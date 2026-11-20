// Render only the requested card numbers from their editable SVG masters.
const { randomUUID } = require('node:crypto');
const { mkdir, readdir, rename, rm, writeFile, readFile, realpath } = require('node:fs/promises');
const { dirname, join, resolve } = require('node:path');
const { createServer } = require('node:http');

const cardSets = {
  unit: { folder: 'Unit Cards', number: /^[A-Z0-9]+-U\d+[A-Z]*$/ },
  tactics: { folder: 'Tactics Cards', number: /^[A-Z0-9]+-T\d+$/ },
};
const edge = { color: '#f8f6ef', width: 3 };

async function replaceFile(path, contents) {
  const temporary = `${path}.${randomUUID()}.tmp`;
  try {
    await writeFile(temporary, contents, { flag: 'wx' });
    await rename(temporary, path);
  } finally {
    await rm(temporary, { force: true });
  }
}

async function render(page, output, kind, number, source, baseURL) {
  await page.goto(`${baseURL}/${encodeURIComponent(source)}`);
  const sourceSize = await page.evaluate(async () => {
    const image = document.querySelector('img');
    await image.decode();
    return [image.naturalWidth, image.naturalHeight];
  });

  await page.goto(`${baseURL}/SVG/${number}.svg`);
  const { size } = await page.evaluate(({ kind, sourceSize, edge }) => {
    const svg = document.documentElement;
    if (svg.localName !== 'svg') throw new Error('Unreadable SVG master');
    const { x, y, width, height } = svg.viewBox.baseVal;
    const [sourceWidth, sourceHeight] = sourceSize;
    const masterHeight = kind === 'tactics' && sourceWidth === 746 && sourceHeight === 1043
      ? 1044
      : sourceHeight;
    if (x || y || width !== sourceWidth || height !== masterHeight) {
      throw new Error(`Expected SVG viewBox 0 0 ${sourceWidth} ${masterHeight}`);
    }
    if (!svg.querySelector('text')) throw new Error('SVG master must contain editable text');
    for (const image of svg.querySelectorAll('image')) {
      const href = image.getAttribute('href') ?? image.getAttributeNS('http://www.w3.org/1999/xlink', 'href');
      if (!href?.startsWith('data:image/')) throw new Error('Embed the artwork in the SVG master');
    }

    const clip = svg.querySelector('clipPath#card-edge');
    const silhouette = clip?.firstElementChild;
    if (clip?.childElementCount !== 1 || silhouette.localName !== 'rect' ||
        silhouette.x.baseVal.value !== x || silhouette.y.baseVal.value !== y ||
        silhouette.width.baseVal.value !== width || silhouette.height.baseVal.value !== height) {
      throw new Error('Define #card-edge as a single full-card rounded rect');
    }
    const inkscape = 'http://www.inkscape.org/namespaces/inkscape';
    const edges = svg.querySelectorAll('#card-edge-stroke');
    if (edges.length > 1) throw new Error('Duplicate #card-edge-stroke layers');
    const previous = edges[0];
    const layerCount = [...svg.children].filter(el =>
      el !== previous && el.getAttributeNS(inkscape, 'groupmode') === 'layer').length;
    const edgeLabel = `Off-white edge (${edge.width} px)`;
    const previousLabel = previous?.getAttributeNS(inkscape, 'label');
    const label = previousLabel?.endsWith(edgeLabel)
      ? previousLabel
      : `${String(layerCount + 1).padStart(2, '0')}  ${edgeLabel}`;
    const layer = document.createElementNS(svg.namespaceURI, 'g');
    layer.setAttribute('id', 'card-edge-stroke');
    layer.setAttributeNS(inkscape, 'inkscape:groupmode', 'layer');
    layer.setAttributeNS(inkscape, 'inkscape:label', label);
    layer.setAttribute('clip-path', 'url(#card-edge)');
    const outline = silhouette.cloneNode(false);
    // Clip away the outer half of the centered stroke.
    outline.removeAttribute('id');
    outline.setAttribute('fill', 'none');
    outline.setAttribute('stroke', edge.color);
    outline.setAttribute('stroke-width', String(2 * edge.width));
    outline.setAttribute('vector-effect', 'non-scaling-stroke');
    layer.append('\n    ', outline, '\n  ');

    if (previous !== svg.lastElementChild || !previous?.isEqualNode(layer)) {
      previous?.remove();
      svg.append('  ', layer, '\n');
    }
    const size = kind === 'unit'
      ? { width: width * 4, height: height * 4 }
      : { width: 3200, height: Math.round(3200 * height / width) };
    // Fill the entire viewport even for a portrait export rounded to a whole pixel.
    svg.setAttribute('preserveAspectRatio', 'none');
    svg.setAttribute('width', size.width);
    svg.setAttribute('height', size.height);
    return { size };
  }, { kind, sourceSize, edge });

  // At deviceScaleFactor 1 the non-scaling stroke is three pixels in the PNG.
  await page.setViewportSize(size);
  await page.evaluate(async () => {
    await document.fonts.ready;
    for (const font of document.fonts) {
      if (font.status === 'error') throw new Error(`Unable to load SVG font ${font.family}`);
    }
  });
  const png = await page.screenshot({ omitBackground: true });
  await page.evaluate(async ({ data, size, edge }) => {
    const image = new Image();
    image.src = data;
    await image.decode();
    const { width, height } = size;
    if (image.width !== width || image.height !== height) throw new Error('Incorrect export size');
    const context = new OffscreenCanvas(width, height).getContext('2d');
    context.drawImage(image, 0, 0);
    const pixel = (x, y) => [...context.getImageData(x, y, 1, 1).data];
    const corners = [[0, 0], [width - 1, 0], [0, height - 1], [width - 1, height - 1]];
    if (corners.some(([x, y]) => pixel(x, y)[3] !== 0)) throw new Error('PNG corners must be transparent');
    const stock = [1, 3, 5].map(start => parseInt(edge.color.slice(start, start + 2), 16)).concat(255);
    const centerX = Math.floor(width / 2);
    const centerY = Math.floor(height / 2);
    for (let inset = 0; inset < edge.width; inset++) {
      const sides = [[centerX, inset], [centerX, height - 1 - inset],
        [inset, centerY], [width - 1 - inset, centerY]];
      if (sides.some(([x, y]) => pixel(x, y).some((channel, i) => channel !== stock[i]))) {
        throw new Error(`PNG does not have a solid ${edge.width}px off-white edge`);
      }
    }
  }, { data: `data:image/png;base64,${png.toString('base64')}`, size, edge });

  const pngPath = join(output, 'PNG', `${number}.png`);
  await mkdir(dirname(pngPath), { recursive: true });
  // Edge normalization is applied in memory; rendering never changes authoring masters.
  await replaceFile(pngPath, png);
  console.log(`Rendered ${number} at ${size.width} × ${size.height}`);
}

async function main() {
  const [kind, ...requested] = process.argv.slice(2);
  if (kind === '--version' && !requested.length) {
    const { chromium } = require('playwright');
    const executablePath = process.env.CARD_RENDER_CHROME;
    const browser = await chromium.launch(executablePath ? { executablePath } : { channel: 'chrome' });
    try {
      console.log(JSON.stringify({ browser: browser.version(), playwright: require('playwright/package.json').version,
        node: process.version }));
    } finally {
      await browser.close();
    }
    return;
  }
  const cardSet = cardSets[kind];
  const numbers = [...new Set(requested.map(number => number.toUpperCase()))];
  if (!cardSet || !numbers.length || numbers.some(number => !cardSet.number.test(number))) {
    throw new Error('Usage: node tools/render_cards.cjs <unit|tactics> <CARD-ID> [CARD-ID ...]');
  }
  const project = resolve(process.env.CARD_RENDER_ROOT || join(__dirname, '..'));
  const root = join(project, 'authoring', 'cards', cardSet.folder);
  const output = join(project, '.build', 'card-renders', cardSet.folder);
  const files = await readdir(root);
  const { chromium } = require('playwright');
  const executablePath = process.env.CARD_RENDER_CHROME;
  // Serve only the requested source files. No checkout browsing or external SVG requests.
  const allowed = new Map();
  const originals = new Map();
  const units = kind === 'unit' ? JSON.parse(await readFile(join(project, 'catalog.json'), 'utf8')) : {};
  for (const number of numbers) {
    const suffix = `${number.toLowerCase()}_en.webp`;
    const sources = files.filter(file => [`img_card_${suffix}`, `img_card_front_${suffix}`].includes(file.toLowerCase()));
    const printed = units[number]?.image;
    const paired = printed === `img_card_front_${suffix}` &&
      sources.includes(printed) && sources.includes(`img_card_${suffix}`);
    if (!paired && sources.length !== 1) throw new Error(`${number}: expected one published English WEBP`);
    const original = paired ? printed : sources[0];
    originals.set(number, original);
    for (const name of [original, `SVG/${number}.svg`]) {
      const path = await realpath(join(root, name));
      const realRoot = await realpath(root);
      if (!path.startsWith(realRoot + require('node:path').sep)) throw new Error('Source may not escape card directory');
      allowed.set(name, await readFile(path));
    }
  }
  const prefix = `/${randomUUID()}/`;
  const server = createServer((request, response) => {
    let name;
    try { name = decodeURIComponent((request.url || '').slice(prefix.length)); } catch {}
    if (request.method !== 'GET' || !request.url?.startsWith(prefix) || !allowed.has(name)) {
      response.writeHead(404); response.end(); return;
    }
    response.writeHead(200, {
      'Content-Type': name.endsWith('.svg') ? 'image/svg+xml' : 'image/webp',
      'Content-Security-Policy': "default-src 'none'; img-src 'self' data:; font-src data:; style-src 'unsafe-inline'",
      'X-Content-Type-Options': 'nosniff',
    });
    response.end(allowed.get(name));
  });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const baseURL = `http://127.0.0.1:${server.address().port}${prefix.slice(0, -1)}`;
  let browser;
  try {
    browser = await chromium.launch(executablePath ? { executablePath } : { channel: 'chrome' });
    const page = await browser.newPage({ deviceScaleFactor: 1, javaScriptEnabled: false });
    await page.route('**/*', route => {
      const url = route.request().url();
      return url.startsWith(baseURL + '/') || url.startsWith('data:') ? route.continue() : route.abort();
    });
    for (const number of numbers) {
      try {
        await render(page, output, kind, number, originals.get(number), baseURL);
      } catch (error) {
        throw new Error(`${number}: ${error.message}`);
      }
    }
  } finally {
    await browser?.close();
    await new Promise(resolve => server.close(resolve));
  }
}

main().catch(error => {
  console.error(error.message);
  process.exitCode = 1;
});
