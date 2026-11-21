varying vec2 texcoord0; // The XY location of the rendering pixel. Starting from {0.0, 0.0} to {1.0, 1.0}
// Note: This version of GLSL uses the built-in variable `gl_FragColor` instead of `out vec4 fragColor;`

#include "colormanagement.glsl"
#include "saturation.glsl"

uniform bool  useSquircleShape; // Whether to use a superellipse/squircle curve for corners.
uniform float squircleBlend;    // How strongly to blend circular corners toward a squircle.

const float squirclePower = 4.0;

/*
 *  \brief Length of a vector under the corner metric: a plain circle, or a circle/superellipse
 *         blend when squircles are enabled. Shared by the window edge (shape_distance) and the
 *         shadow (getShadowByDistance) so both round their corners with the same shape.
 *  \param point: The XY point being shaded.
 *  \param center: The XY center of the corner roundness.
 *  \return The blended length.
 */
float squircle_distance(vec2 point, vec2 center)
{
    vec2  delta    = point - center;
    vec2  d        = abs(delta);
    float circle   = length(d);
    float squircle = pow(pow(d.x, squirclePower) + pow(d.y, squirclePower), 1.0 / squirclePower);

    return mix(circle, squircle, squircleBlend);
}

/*
 *  \brief Magnitude of the gradient of squircle_length. The superellipse blend is not a true
 *         signed-distance field, so its gradient dips below 1 toward the diagonal; shape_distance
 *         divides by this so the outline and antialiasing bands stay a uniform width all around.
 *  \param point: The XY point being shaded.
 *  \param center: The XY center of the corner roundness.
 *  \return The gradient magnitude (1.0 for the plain-circle case).
 */
float squircle_gradient(vec2 point, vec2 center)
{
    vec2  delta              = point - center;
    vec2  d                  = abs(delta);
    float circle             = length(d);
    float squircle           = pow(pow(d.x, squirclePower) + pow(d.y, squirclePower), 1.0 / squirclePower);
    vec2  circle_gradient    = (circle > 0.0) ? d / circle : vec2(0.0);
    vec2  squircle_gradient_ = (squircle > 0.0) ? pow(d / squircle, vec2(squirclePower - 1.0)) : vec2(0.0);

    return length(mix(circle_gradient, squircle_gradient_, squircleBlend));
}
uniform sampler2D sampler;            // The painted contents of the window.
uniform float     radius;             // The thickness of the outline in pixels specified in settings.
uniform vec2      windowSize;         // Containing `window->frameGeometry().size()`
uniform vec2      windowExpandedSize; // Containing `window->expandedGeometry().size()`

uniform vec2 windowTopLeft; /* The distance between the top-left of `expandedGeometry` and
                             * the top-left of `frameGeometry`. When `windowTopLeft = {0,0}`, it means
                             * `expandedGeometry = frameGeometry` and there is no shadow. */

uniform vec4  outlineColor1;          // The RGBA of the outline's first gradient stop specified in settings.
uniform vec4  outlineColor2;          // The RGBA of the outline's second gradient stop. Equals stop 1 when not a gradient.
uniform float outlineAngle;           // The outline gradient angle in degrees. 0 = left->right, 90 = top->bottom.
uniform float outlineThickness;       // The thickness of the outline in pixels specified in settings.
uniform vec4  secondOutlineColor1;    // The RGBA of the second outline's first gradient stop specified in settings.
uniform vec4  secondOutlineColor2;    // The RGBA of the second outline's second gradient stop.
uniform float secondOutlineAngle;     // The second outline gradient angle in degrees.
uniform float secondOutlineThickness; // The thickness of the second outline in pixels specified in settings.
uniform vec4  outerOutlineColor1;     // The RGBA of the outer outline's first gradient stop specified in settings.
uniform vec4  outerOutlineColor2;     // The RGBA of the outer outline's second gradient stop.
uniform float outerOutlineAngle;      // The outer outline gradient angle in degrees.
uniform float outerOutlineThickness;  // The thickness of the outer outline in pixels specified in settings.

vec2 tex_to_pixel(vec2 texcoord)
{
    return vec2(texcoord.x * windowExpandedSize.x - windowTopLeft.x,
                (1.0 - texcoord.y) * windowExpandedSize.y - windowTopLeft.y);
}
vec2 pixel_to_tex(vec2 pixelcoord)
{
    return vec2((pixelcoord.x + windowTopLeft.x) / windowExpandedSize.x,
                1.0 - (pixelcoord.y + windowTopLeft.y) / windowExpandedSize.y);
}
bool hasExpandedSize() { return windowTopLeft.x >= 1.0 && windowTopLeft.y >= 1.0; }
bool hasPrimaryOutline() { return outlineColor1.a > 0.0 && outlineThickness > 0.0; }
bool hasSecondOutline() { return secondOutlineColor1.a > 0.0 && secondOutlineThickness > 0.0; }
bool hasOuterOutline() { return hasExpandedSize() && outerOutlineColor1.a > 0.0 && outerOutlineThickness > 0.0; }

uniform bool  usesNativeShadows;
uniform vec4  shadowColor; // The RGBA of the shadow color specified in settings.
uniform float shadowSize;  // The shadow size specified in settings.

bool isDrawingShadows() { return hasExpandedSize() && (usesNativeShadows || shadowColor.a > 0.0); }

float parametricBlend(float t)
{
    float sqt = t * t;
    return sqt / (2.0 * (sqt - t) + 1.0);
}

/*
 *  \brief This function generates the shadow color based on the distance_from_center
 *  \param coord0: The XY point
 *  \param center: The origin XY point that is being used as a reference for the center of shadow darkness.
 *  \return The RGBA color to be used for the shadow.
 */
vec4 getShadowByDistance(vec2 coord0, vec2 center)
{
    float distance_from_center;
    if (useSquircleShape) {
        distance_from_center = squircle_distance(coord0, center);
    } else {
        distance_from_center = distance(coord0, center);
    }

    float percent = 1.0 - distance_from_center / shadowSize;
    percent       = clamp(percent, 0.0, 1.0);
    percent       = parametricBlend(percent);
    if (percent < 0.0) {
        return vec4(0.0, 0.0, 0.0, 0.0);
    }
    return vec4(shadowColor.rgb * shadowColor.a * percent, shadowColor.a * percent);
}

vec4 getCustomShadow(vec2 coord0, float r)
{
    float shadowShiftX   = sqrt(shadowSize);
    float shadowShiftTop = sqrt(shadowSize);

    /*
        Split the window into these sections below. They will have a different center of circle for rounding.

        TL  T   T   TR
        L   x   x   R
        L   x   x   R
        BL  B   B   BR
    */
    if (coord0.y < r + shadowShiftTop) {
        if (coord0.x < r + shadowShiftX) {
            return getShadowByDistance(coord0, vec2(r + shadowShiftX, r + shadowShiftTop)); // Section TL
        } else if (coord0.x > windowSize.x - r - shadowShiftX) {
            return getShadowByDistance(coord0, vec2(windowSize.x - r - shadowShiftX, r + shadowShiftTop)); // Section TR
        } else if (coord0.y < 0.0) {
            return getShadowByDistance(coord0, vec2(coord0.x, r + shadowShiftTop)); // Section T
        }
    } else if (coord0.y > windowSize.y - r) {
        if (coord0.x < r + shadowShiftX) {
            return getShadowByDistance(coord0, vec2(r + shadowShiftX, windowSize.y - r)); // Section BL
        } else if (coord0.x > windowSize.x - r - shadowShiftX) {
            return getShadowByDistance(coord0, vec2(windowSize.x - r - shadowShiftX, windowSize.y - r)); // Section BR
        } else if (coord0.y > windowSize.y) {
            return getShadowByDistance(coord0, vec2(coord0.x, windowSize.y - r)); // Section B
        }
    } else {
        if (coord0.x < 0.0) {
            return getShadowByDistance(coord0, vec2(r + shadowShiftX, coord0.y)); // Section L
        } else if (coord0.x > windowSize.x) {
            return getShadowByDistance(coord0, vec2(windowSize.x - r - shadowShiftX, coord0.y)); // Section R
        }
        // For section x, the tex is not changing
    }
    return vec4(0.0, 0.0, 0.0, 0.0);
}

vec4 getNativeShadow(vec2 coord0, float r, vec4 default_tex)
{
    float margin_edge  = 2.0;
    float margin_point = margin_edge + 1.0;

    /*
        Split the window into these sections below. They will have a different center of circle for rounding.

        TL  T   T   TR
        L   x   x   R
        L   x   x   R
        BL  B   B   BR
    */
    if (coord0.y >= -margin_edge && coord0.y <= r) {
        if (coord0.x >= -margin_edge && coord0.x <= r) {
            vec2 a       = vec2(-margin_point, coord0.y + coord0.x + margin_point);
            vec2 b       = vec2(coord0.x + coord0.y + margin_point, -margin_point);
            vec4 a_color = texture2D(sampler, pixel_to_tex(a));
            vec4 b_color = texture2D(sampler, pixel_to_tex(b));
            return mix(a_color, b_color, distance(a, coord0) / distance(a, b)); // Section TL

        } else if (coord0.x <= windowSize.x + margin_edge && coord0.x >= windowSize.x - r) {
            vec2 a       = vec2(windowSize.x + margin_point, coord0.y + (windowSize.x - coord0.x) + margin_point);
            vec2 b       = vec2(coord0.x - coord0.y - margin_point, -margin_point);
            vec4 a_color = texture2D(sampler, pixel_to_tex(a));
            vec4 b_color = texture2D(sampler, pixel_to_tex(b));
            return mix(a_color, b_color, distance(a, coord0) / distance(a, b)); // Section TR
        }
    } else if (coord0.y <= windowSize.y + margin_edge && coord0.y >= windowSize.y - r) {
        if (coord0.x >= -margin_edge && coord0.x <= r) {
            vec2 a       = vec2(-margin_point, coord0.y - coord0.x - margin_point);
            vec2 b       = vec2(coord0.x + (windowSize.y - coord0.y) + margin_point, windowSize.y + margin_point);
            vec4 a_color = texture2D(sampler, pixel_to_tex(a));
            vec4 b_color = texture2D(sampler, pixel_to_tex(b));
            return mix(a_color, b_color, distance(a, coord0) / distance(a, b)); // Section BL

        } else if (coord0.x <= windowSize.x + margin_edge && coord0.x >= windowSize.x - r) {
            vec2 a       = vec2(windowSize.x + margin_point, coord0.y - (windowSize.x - coord0.x) - margin_point);
            vec2 b       = vec2(coord0.x - (windowSize.y - coord0.y) - margin_point, windowSize.y + margin_point);
            vec4 a_color = texture2D(sampler, pixel_to_tex(a));
            vec4 b_color = texture2D(sampler, pixel_to_tex(b));
            return mix(a_color, b_color, distance(a, coord0) / distance(a, b)); // Section BR
        }
    }
    return default_tex;
}

/*
 *  \brief This function is used to choose the pixel shadow color based on the XY pixel and corner radius.
 *  \param coord0: The XY point
 *  \param r: The radius of corners in pixel.
 *  \return The RGBA color to be used for the shadow.
 */
vec4 getShadow(vec2 coord0, float r, vec4 default_tex)
{
    if (!isDrawingShadows()) {
        if (hasExpandedSize()) {
            // Preserve RGB so anti-aliasing only fades alpha (fix for #430)
            return vec4(default_tex.rgb, 0.0);
        }
        // Windows without a shadow buffer (e.g. CSD XWayland apps like Steam)
        // need premultiplied-valid output or the compositor brightens edge pixels (#491)
        return vec4(0.0, 0.0, 0.0, 0.0);
    } else if (usesNativeShadows) {
        return getNativeShadow(coord0, r, default_tex);
    } else {
        return getCustomShadow(coord0, r);
    }
}

bool is_within(float point, float a, float b) { return (point >= min(a, b) && point <= max(a, b)); }
bool is_within(vec2 point, vec2 corner_a, vec2 corner_b)
{
    return is_within(point.x, corner_a.x, corner_b.x) && is_within(point.y, corner_a.y, corner_b.y);
}

/*
 *  \brief Distance from a point to a corner center, as a circular arc or a squircle curve.
 *  \param point: The XY point being shaded.
 *  \param center: The XY center of the corner roundness.
 *  \param radius: The corner radius in pixels.
 *  \return A field whose value equals `radius` on the corner boundary.
 */
float shape_distance(vec2 point, vec2 center, float radius)
{
    if (!useSquircleShape) {
        return distance(point, center);
    }

    // Pure circle/superellipse blend: on a straight edge the offset is axis-aligned, so this
    // equals distance(point, center) and leaves the edge undistorted; only the corners curve.
    float dist = squircle_distance(point, center);

    // Renormalize to ~unit gradient so the outline and antialiasing bands keep a uniform
    // width at the corners, where the raw superellipse gradient would otherwise dip below 1.
    float grad = squircle_gradient(point, center);
    return radius + (dist - radius) / max(grad, 1e-4);
}

/*
 *  \brief Linear gradient color sampled along an axis across the window frame.
 *  \param c1: The color at the start of the gradient.
 *  \param c2: The color at the end of the gradient. When equal to c1 this returns a solid color.
 *  \param angleDeg: The gradient direction in degrees. 0 = left->right, 90 = top->bottom.
 *  \param coord0: The XY pixel being shaded, in window-frame pixels (see tex_to_pixel).
 *  \return The interpolated RGBA color at that pixel.
 */
vec4 gradientColor(vec4 c1, vec4 c2, float angleDeg, vec2 coord0)
{
    vec2  dir = vec2(cos(radians(angleDeg)), sin(radians(angleDeg)));
    float t   = dot(coord0 / windowSize - 0.5, dir) + 0.5;
    return mix(c1, c2, clamp(t, 0.0, 1.0));
}

/*
 *  \brief This function is used to choose the pixel color based on its distance to the center input.
 *  \param coord0: The XY point
 *  \param tex: The RGBA color of the pixel in XY
 *  \param start: The reference XY point to determine the center of the corner roundness.
 *  \param angle: The angle in radians to move away from the start point to determine the center of the corner roundness.
 *  \param is_corner: Boolean to know if its a corner or an edge
 *  \param coord_shadowColor: The RGBA color of the shadow of the pixel behind the window.
 *  \return The RGBA color to be used instead of tex input.
 */
vec4 shapeCorner(vec2 coord0, vec4 tex, vec2 start, float angle, vec4 coord_shadowColor)
{
    // Resolve each outline's gradient once; the logic below then treats them as solid colors.
    // When an outline is not a gradient its two stops are equal, so these collapse to plain solids.
    vec4 outlineColor       = gradientColor(outlineColor1, outlineColor2, outlineAngle, coord0);
    vec4 secondOutlineColor = gradientColor(secondOutlineColor1, secondOutlineColor2, secondOutlineAngle, coord0);
    vec4 outerOutlineColor  = gradientColor(outerOutlineColor1, outerOutlineColor2, outerOutlineAngle, coord0);

    vec2  angle_vector         = vec2(cos(angle), sin(angle));
    float corner_length        = (abs(angle_vector.x) < 0.1 || abs(angle_vector.y) < 0.1) ? 1.0 : sqrt(2.0);
    vec2  roundness_center     = start + radius * angle_vector * corner_length;
    vec2  outlineStart         = start + outlineThickness * angle_vector * corner_length;
    vec2  secondOutlineStart   = start + (outlineThickness + secondOutlineThickness) * angle_vector * corner_length;
    vec2  outerOutlineEnd      = start - outerOutlineThickness * angle_vector * corner_length;
    float distance_from_center = shape_distance(coord0, roundness_center, radius);
    bool  inOutlineZone =
            (hasPrimaryOutline() && outlineThickness >= radius && is_within(coord0, outlineStart, start)) ||
            (hasSecondOutline() && outlineThickness + secondOutlineThickness >= radius &&
             is_within(coord0, secondOutlineStart, start));

    if (hasOuterOutline()) {
        vec4 outerOutlineOverlay = mix(coord_shadowColor, outerOutlineColor, outerOutlineColor.a);
        if (distance_from_center > radius + outerOutlineThickness - 0.5) {
            // antialiasing for the outer outline to shadow
            float antialiasing = clamp(distance_from_center - radius - outerOutlineThickness + 0.5, 0.0, 1.0);
            return mix(outerOutlineOverlay, coord_shadowColor, antialiasing);
        } else if (!inOutlineZone && distance_from_center > radius - 0.5) {
            // antialiasing for the outer outline to the window edge
            float antialiasing = clamp(distance_from_center - radius + 0.5, 0.0, 1.0);
            if (hasPrimaryOutline()) {
                // if the primary outline is present
                vec4 outlineOverlay = vec4(mix(tex.rgb, outlineColor.rgb, outlineColor.a), 1.0);
                return mix(outlineOverlay, outerOutlineOverlay, antialiasing);
            } else if (hasSecondOutline()) {
                // if the second outline is present
                vec4 secondOutlineOverlay = vec4(mix(tex.rgb, secondOutlineColor.rgb, secondOutlineColor.a), 1.0);
                return mix(secondOutlineOverlay, outerOutlineOverlay, antialiasing);
            } else {
                // if the no other outline is not present
                return mix(tex, outerOutlineOverlay, antialiasing);
            }
        }
    } else {
        if (!inOutlineZone && distance_from_center > radius - 0.5) {
            // antialiasing for the outer outline to the window edge
            float antialiasing = clamp(distance_from_center - radius + 0.5, 0.0, 1.0);
            if (hasPrimaryOutline()) {
                // if the primary outline is present
                vec4 outlineOverlay = vec4(mix(tex.rgb, outlineColor.rgb, outlineColor.a), 1.0);
                return mix(outlineOverlay, coord_shadowColor, antialiasing);
            } else if (hasSecondOutline()) {
                // if the second outline is present
                vec4 secondOutlineOverlay = vec4(mix(tex.rgb, secondOutlineColor.rgb, secondOutlineColor.a), 1.0);
                return mix(secondOutlineOverlay, coord_shadowColor, antialiasing);
            } else {
                // if the no other outline is not present
                return mix(tex, coord_shadowColor, antialiasing);
            }
        }
    }

    if (hasPrimaryOutline()) {
        vec4 outlineOverlay = vec4(mix(tex.rgb, outlineColor.rgb, outlineColor.a), 1.0);

        if (outlineThickness >= radius && is_within(coord0, outlineStart, start)) {
            // when the outline is bigger than the roundness radius
            // from the window to the outline is sharp
            // no antialiasing is needed because it is not round
            return outlineOverlay;
        } else if (distance_from_center > radius - outlineThickness - 0.5) {
            // from the window to the outline
            float antialiasing = clamp(distance_from_center - radius + outlineThickness + 0.5, 0.0, 1.0);
            if (hasSecondOutline()) {
                vec4 secondOutlineOverlay = vec4(mix(tex.rgb, secondOutlineColor.rgb, secondOutlineColor.a), 1.0);
                return mix(secondOutlineOverlay, outlineOverlay, antialiasing);
            } else {
                return mix(tex, outlineOverlay, antialiasing);
            }
        }
    }

    if (hasSecondOutline()) {
        vec4 secondOutlineOverlay = vec4(mix(tex.rgb, secondOutlineColor.rgb, secondOutlineColor.a), 1.0);

        if (outlineThickness + secondOutlineThickness >= radius && is_within(coord0, secondOutlineStart, start)) {
            // when the outline is bigger than the roundness radius
            // from the window to the outline is sharp
            // no antialiasing is needed because it is not round
            return secondOutlineOverlay;
        } else if (distance_from_center > radius - outlineThickness - secondOutlineThickness - 0.5) {
            // from the window to the outline
            float antialiasing =
                    clamp(distance_from_center - radius + outlineThickness + secondOutlineThickness + 0.5, 0.0, 1.0);
            return mix(tex, secondOutlineOverlay, antialiasing);
        }
    }

    // if other conditions don't apply, just don't draw an outline, from the window to the shadow
    float antialiasing = clamp(radius - distance_from_center + 0.5, 0.0, 1.0);
    return mix(coord_shadowColor, tex, antialiasing);
}

vec4 run(vec2 texcoord0, vec4 tex)
{
    if (tex.a == 0.0) {
        return tex;
    }

    float r = max(radius, outlineThickness);

    /* Since `texcoord0` is ranging from {0.0, 0.0} to {1.0, 1.0} is not pixel intuitive,
     * I am changing the range to become from {0.0, 0.0} to {width, height}
     * in a way that {0,0} is the top-left of the window and not its shadow.
     * This means areas with negative numbers and areas beyond windowSize is considered part of the shadow. */
    vec2 coord0 = tex_to_pixel(texcoord0);

    vec4 coord_shadowColor = getShadow(coord0, r, tex);

    /*
        Split the window into these sections below. They will have a different center of circle for rounding.

        TL  T   T   TR
        L   x   x   R
        L   x   x   R
        BL  B   B   BR
    */
    if (coord0.y < r) {
        if (coord0.x < r) {
            return shapeCorner(coord0, tex, vec2(0.0, 0.0), radians(45.0), coord_shadowColor); // Section TL
        } else if (coord0.x > windowSize.x - r) {
            return shapeCorner(coord0, tex, vec2(windowSize.x, 0.0), radians(135.0), coord_shadowColor); // Section TR
        } else if (coord0.y < outlineThickness + secondOutlineThickness) {
            return shapeCorner(coord0, tex, vec2(coord0.x, 0.0), radians(90.0), coord_shadowColor); // Section T
        }
    } else if (coord0.y > windowSize.y - r) {
        if (coord0.x < r) {
            return shapeCorner(coord0, tex, vec2(0.0, windowSize.y), radians(315.0), coord_shadowColor); // Section BL
        } else if (coord0.x > windowSize.x - r) {
            return shapeCorner(coord0, tex, vec2(windowSize.x, windowSize.y), radians(225.0),
                               coord_shadowColor); // Section BR
        } else if (coord0.y > windowSize.y - outlineThickness - secondOutlineThickness) {
            return shapeCorner(coord0, tex, vec2(coord0.x, windowSize.y), radians(270.0),
                               coord_shadowColor); // Section B
        }
    } else {
        if (coord0.x < r) {
            return shapeCorner(coord0, tex, vec2(0.0, coord0.y), radians(0.0), coord_shadowColor); // Section L
        } else if (coord0.x > windowSize.x - r) {
            return shapeCorner(coord0, tex, vec2(windowSize.x, coord0.y), radians(180.0),
                               coord_shadowColor); // Section R
        }
        // For section x, the tex is not changing
    }
    return tex;
}

uniform vec4 modulation; // This variable is assigned and used by KWinEffects used for proper fading.

void main(void)
{
    vec4 tex = texture2D(sampler, texcoord0);

    tex = run(texcoord0, tex);

    tex = sourceEncodingToNitsInDestinationColorspace(tex);
    tex = adjustSaturation(tex);
    tex *= modulation;

    gl_FragColor = nitsToDestinationEncoding(tex);
}
