// Runs in an isolated JavaScript context. Coordinates are Z-up.
const { Body, Box, ConvexPolyhedron, Quaternion, SAPBroadphase, Vec3, World } = CANNON;
const floorZ = new Vec3(0, 0, 1);
const dt = 1 / 120;
const pole = 1.2;
const cosine = Math.cos(Math.PI / 5);
const zigzag = pole * (1 - cosine) / (1 + cosine);
const vertices = Array.from({ length: 10 }, (_, index) => {
    const angle = index * Math.PI / 5;
    return new Vec3(Math.cos(angle), Math.sin(angle), index % 2 === 0 ? zigzag : -zigzag);
});
vertices.push(new Vec3(0, 0, pole), new Vec3(0, 0, -pole));
const faces = Array.from({ length: 10 }, (_, i) => {
    const face = [i, (i + 1) % 10, i % 2 === 0 ? 11 : 10, (i + 9) % 10];
    const [a, b, c] = face.map(index => vertices[index]);
    return b.vsub(a).cross(c.vsub(a)).dot(a) < 0 ? face.reverse() : face;
});
const shape = new ConvexPolyhedron({ vertices, faces });
// Opposite faces sum to 11. A random rotation/reflection of these labels on
// each body makes the dice fair even if a launch or solver favors an orientation.
const faceNumbers = [1, 8, 2, 7, 5, 10, 3, 9, 4, 6];
const geometry = JSON.stringify([vertices.map(v => [v.x, v.y, v.z]), faces, faceNumbers]);
const normal = new Vec3();
let world, dice, elapsed, trayWidth, trayHeight, settledFaces, retryAt;

function addBox(x, y, z, sx, sy, sz) {
    world.addBody(new Body({ position: new Vec3(x, y, z), shape: new Box(new Vec3(sx, sy, sz)) }));
}

function randomOrientation() {
    const u = Math.random();
    const a = Math.random() * 2 * Math.PI;
    const b = Math.random() * 2 * Math.PI;
    return new Quaternion(Math.sqrt(1 - u) * Math.sin(a), Math.sqrt(1 - u) * Math.cos(a),
                          Math.sqrt(u) * Math.sin(b), Math.sqrt(u) * Math.cos(b));
}

function startDice(width, height, count) {
    elapsed = 0;
    trayWidth = width;
    trayHeight = height;
    settledFaces = Array(count).fill(null);
    retryAt = 6;
    world = new World({ gravity: new Vec3(0, 0, -25), allowSleep: true });
    world.broadphase = new SAPBroadphase(world);
    world.defaultContactMaterial.friction = .42;
    world.defaultContactMaterial.restitution = .38;
    world.solver.iterations = 12;
    addBox(0, 0, -.6, width / 2 + 1, height / 2 + 1, .6);
    for (const side of [-1, 1]) {
        addBox(side * (width / 2 + .5), 0, 3, .5, height / 2 + 1, 3);
        addBox(0, side * (height / 2 + .5), 3, width / 2 + 1, .5, 3);
    }
    const rows = Math.min(count, Math.max(1, Math.floor((height - 2) / 2.7)));
    const columns = Math.ceil(count / rows);
    const spacing = Math.min(3.2, (width - 4) / Math.max(1, columns));
    dice = Array.from({ length: count }, (_, index) => {
        const row = index % rows;
        const column = Math.floor(index / rows);
        const y = (row - (rows - 1) / 2) * Math.min(3.1, (height - 3) / rows);
        const x = -width / 2 + 1.65 + spacing * column;
        const direction = count >= 16 && column > 0 && (row + column) % 2 ? -1 : 1;
        const speed = count < 16 ? 7 + 6 * Math.random() : 4 + 4 * Math.random();
        const die = new Body({
            mass: 1, shape, position: new Vec3(x, y, 2.8 + Math.random() * 1.4),
            quaternion: randomOrientation(),
            velocity: new Vec3(direction * speed, (Math.random() - .5) * 10, 1 + Math.random() * 3),
            angularVelocity: new Vec3((Math.random() - .5) * 32, (Math.random() - .5) * 32, (Math.random() - .5) * 32),
            linearDamping: .34, angularDamping: .46, sleepSpeedLimit: .31, sleepTimeLimit: .22,
        });
        world.addBody(die);
        return die;
    });
    return true;
}

function faceUp(die) {
    let highest = -Infinity;
    let index = 0;
    shape.faceNormals.forEach((candidate, i) => {
        die.quaternion.vmult(candidate, normal);
        if (normal.dot(floorZ) > highest) {
            index = i;
            highest = normal.z;
        }
    });
    return { index, alignment: highest };
}

function openSpot() {
    let bestSpace = -Infinity;
    let targetX = 0, targetY = 0;
    for (let attempt = 0; attempt < 32; attempt++) {
        const x = (Math.random() - .5) * (trayWidth - 5);
        const y = (Math.random() - .5) * (trayHeight - 5);
        const space = Math.min(...dice.map(other => (x - other.position.x) ** 2 + (y - other.position.y) ** 2));
        if (space > bestSpace) {
            bestSpace = space;
            targetX = x;
            targetY = y;
        }
    }
    return [targetX, targetY];
}

function rerollCocked(die, lift) {
    // Send cocked dice toward free space so they do not keep landing in the pile.
    const [x, y] = openSpot();
    die.wakeUp();
    if (lift) {
        // Pick up dice that stay jammed and drop them back into the tray.
        die.position.set(x, y, 1.85);
        die.quaternion.copy(randomOrientation());
        die.velocity.set(0, 0, -1);
        die.angularVelocity.set(1.5, -1.5, 1);
        die.angularDamping = .76;
        die.linearDamping = .68;
        die.aabbNeedsUpdate = true;
    } else {
        die.velocity.set((x - die.position.x) / .76, (y - die.position.y) / .76, 10);
        die.angularVelocity.set(5, -5, 3);
    }
}

function stepDice(steps) {
    for (let i = 0; i < steps; i++) {
        world.step(dt);
        elapsed += dt;
    }
    if (elapsed >= 16) throw new Error('The dice did not settle. Close the tray and roll again.');
    const lift = elapsed >= retryAt;
    if (lift) {
        retryAt += 3;
        world.defaultContactMaterial.restitution = .1;
    }
    dice.forEach((die, index) => {
        if (settledFaces[index] !== null) return;
        if (die.sleepState === Body.SLEEPING) {
            const top = faceUp(die);
            if (top.alignment >= .97 && die.position.z < .86) {
                settledFaces[index] = top.index;
                // Read flat dice in place. They still act as obstacles for the other dice.
                die.type = Body.STATIC;
                die.mass = 0;
                die.updateMassProperties();
                return;
            }
            rerollCocked(die, elapsed >= 6);
        } else if (lift) {
            rerollCocked(die, true);
        }
    });
    const poses = dice.map(die => [die.position.x, die.position.y, die.position.z,
                                 die.quaternion.x, die.quaternion.y, die.quaternion.z, die.quaternion.w]);
    return JSON.stringify([poses, settledFaces.includes(null) ? null : settledFaces]);
}
