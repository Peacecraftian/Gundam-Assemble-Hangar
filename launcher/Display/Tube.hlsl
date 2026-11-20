// WPF supplies the already-composited visual tree as sampler 0.
sampler2D screen : register(s0);
float2 pixel : register(c0);
// x is the rolling refresh line's screen position; y is phosphor gain.
float2 refresh : register(c1);
float4 main(float2 uv : TEXCOORD0) : COLOR0
{
    float2 p = uv * 2 - 1;
    float radius = dot(p, p);
    float2 sampleUV = uv + p * radius * 0.0023;
    float3 phosphor = tex2D(screen, sampleUV).rgb;
    float2 spread = pixel * 2.3;
    float3 glow = tex2D(screen, sampleUV + spread).rgb
                + tex2D(screen, sampleUV - spread).rgb
                + tex2D(screen, sampleUV + float2(spread.x,-spread.y)).rgb
                + tex2D(screen, sampleUV - float2(spread.x,-spread.y)).rgb;
    float scan = abs(frac(sampleUV.y / (pixel.y * 3.5)) * 2 - 1);
    float shade = (0.90 + 0.10 * scan) * (1 - 0.055 * radius * radius);
    float offset = sampleUV.y - refresh.x;
    float band = saturate(1 - abs(offset) * 37);
    float rim = saturate(1 - abs(offset + 0.006) * 360);
    float3 light = (phosphor + glow * 0.055) * shade * refresh.y;
    light *= 1 - 0.10 * band * band;
    light += float3(0.009, 0.018, 0.012) * rim;
    return float4(saturate(light), 1);
}
