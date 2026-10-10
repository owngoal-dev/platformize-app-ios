#!/usr/bin/env python3
"""Turn an Icon Composer icon into a plain app icon set of three JPEGs.

An `AppIcon.icon` compiles, through actool, into three 1024x1024 lossless
renders (any, dark, tinted) stored once for the phone idiom and again for the
pad: iGhostVT's `Assets.car` was 5,103,512 bytes, 4.3 MB of it those six
renditions (`xcrun assetutil --info Assets.car`, Xcode 27). No build setting
drops them — not `ASSETCATALOG_COMPILER_STANDALONE_ICON_BEHAVIOR`,
`--optimization space`, the deployment target, SVG layers or one target
device — and Apple closed the report as working as designed (FB20957000).
App Store thinning would keep one idiom; a deb or a sideloaded .ipa ships
both.

This keeps actool's own renders and ships them as the icon. It compiles the
icon once, reads the three renders back out of the catalogue (CoreUI's
`CUICatalog`, private, so this runs on a Mac with Xcode and never in an app),
encodes each as JPEG and writes an `AppIcon.appiconset` beside a
`Contents.json` that lists them as any, dark and tinted. actool stores a JPEG
in an icon set as it is: iGhostVT's catalogue went to 442,040 bytes. On iOS 26
the home screen glazes the flat images itself and draws them like the layered
icon in all four appearances (compared on a device, screenshot against
screenshot); what goes is the layered icon's live glass. Mac Catalyst derives
its `.icns` from the same image with the same margins.

JPEG goes through ImageMagick at 4:4:4 when `magick` is on PATH; otherwise
`sips`, which subsamples to 4:2:0 and writes files about half as large again.
Never reduce the colours instead: 64 colours bands visibly, and the asset
catalogue's own `lossy` compression is RGB555.

Keep the `.icon` in the repository as the source (`Documents/Icon/`), out of
every target, and run this again after editing it.

Usage: render-app-icon.py <AppIcon.icon> <AppIcon.appiconset> [--quality 92]

Exit 0 written, 64 bad arguments, 65 a render is missing or not opaque,
66 a tool failed.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

APPEARANCES = [
    # (CoreUI appearance name, file name, Contents.json appearances)
    ("UIAppearanceAny", "AppIcon.jpg", None),
    ("UIAppearanceDark", "AppIcon-dark.jpg", [{"appearance": "luminosity", "value": "dark"}]),
    ("ISAppearanceTintable", "AppIcon-tinted.jpg", [{"appearance": "luminosity", "value": "tinted"}]),
]

EXTRACTOR = r"""
#import <Foundation/Foundation.h>
#import <CoreGraphics/CoreGraphics.h>
#import <ImageIO/ImageIO.h>
#import <objc/message.h>
#include <dlfcn.h>

@interface CUICatalog : NSObject
- (instancetype)initWithURL:(NSURL *)url error:(NSError **)error;
- (id)iconImageWithName:(NSString *)n scaleFactor:(double)s deviceIdiom:(long long)i
          deviceSubtype:(unsigned long long)st displayGamut:(long long)g
        layoutDirection:(long long)l sizeClassHorizontal:(long long)h
      sizeClassVertical:(long long)v desiredSize:(CGSize)size appearanceName:(NSString *)a;
@end

// argv: car, icon name, output directory, appearance names...
int main(int argc, char **argv) {
    @autoreleasepool {
        if (argc < 5 || !dlopen("/System/Library/PrivateFrameworks/CoreUI.framework/CoreUI", RTLD_NOW)) return 2;
        CUICatalog *catalog = [[NSClassFromString(@"CUICatalog") alloc]
            initWithURL:[NSURL fileURLWithPath:@(argv[1])] error:nil];
        if (!catalog) return 3;
        for (int k = 4; k < argc; k++) {
            NSString *appearance = @(argv[k]);
            id image = [catalog iconImageWithName:@(argv[2]) scaleFactor:1 deviceIdiom:1 deviceSubtype:0
                                     displayGamut:0 layoutDirection:0 sizeClassHorizontal:0
                                sizeClassVertical:0 desiredSize:CGSizeMake(1024, 1024)
                                   appearanceName:appearance];
            if (![image respondsToSelector:@selector(image)]) return 4;
            CGImageRef cg = ((CGImageRef (*)(id, SEL))objc_msgSend)(image, @selector(image));
            if (!cg || CGImageGetWidth(cg) != 1024 || CGImageGetHeight(cg) != 1024) return 4;
            NSString *path = [NSString stringWithFormat:@"%s/%@.png", argv[3], appearance];
            CGImageDestinationRef out = CGImageDestinationCreateWithURL(
                (__bridge CFURLRef)[NSURL fileURLWithPath:path], CFSTR("public.png"), 1, NULL);
            CGImageDestinationAddImage(out, cg, NULL);
            if (!CGImageDestinationFinalize(out)) return 5;
            CFRelease(out);
        }
    }
    return 0;
}
"""


def fail(message, code):
    print(f"render-app-icon: {message}", file=sys.stderr)
    sys.exit(code)


def run(command, what):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        fail(f"{what} failed ({result.returncode}): {(result.stderr or result.stdout).strip()[-800:]}", 66)
    return result.stdout


def opaque(png):
    """Every pixel opaque. Without ImageMagick the render is trusted: CoreUI
    hands back the full-bleed square actool made for the home screen to mask."""
    if shutil.which("magick"):
        return run(["magick", png, "-format", "%[opaque]", "info:"], "magick").strip().lower() == "true"
    return True


def encode(png, jpeg, quality):
    if shutil.which("magick"):
        run(["magick", png, "-alpha", "off", "-sampling-factor", "4:4:4",
             "-quality", str(quality), jpeg], "magick")
        psnr = subprocess.run(["magick", "compare", "-metric", "PSNR", png, jpeg, "null:"],
                              capture_output=True, text=True).stderr.split()
        return psnr[0] if psnr else "?"
    run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", str(quality), png, "--out", jpeg], "sips")
    return "? (sips, 4:2:0)"


def main():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("icon")
    parser.add_argument("iconset")
    parser.add_argument("--quality", type=int, default=92)
    args = parser.parse_args()

    icon = os.path.abspath(args.icon.rstrip("/"))
    iconset = os.path.abspath(args.iconset.rstrip("/"))
    if not icon.endswith(".icon") or not os.path.isfile(os.path.join(icon, "icon.json")):
        fail(f"{args.icon} is not an Icon Composer document", 64)
    if not iconset.endswith(".appiconset"):
        fail(f"{args.iconset} must name an .appiconset folder", 64)
    if not 50 <= args.quality <= 100:
        fail("--quality is 50–100", 64)
    name = os.path.splitext(os.path.basename(icon))[0]

    with tempfile.TemporaryDirectory() as temp:
        compiled = os.path.join(temp, "compiled")
        os.mkdir(compiled)
        run(["xcrun", "actool", icon, "--compile", compiled, "--platform", "iphoneos",
             "--minimum-deployment-target", "15.0", "--target-device", "iphone",
             "--target-device", "ipad", "--app-icon", name,
             "--output-partial-info-plist", os.path.join(temp, "partial.plist"),
             "--output-format", "human-readable-text"], "actool")
        car = os.path.join(compiled, "Assets.car")
        if not os.path.isfile(car):
            fail("actool wrote no Assets.car", 66)

        source = os.path.join(temp, "extract.m")
        binary = os.path.join(temp, "extract")
        with open(source, "w") as handle:
            handle.write(EXTRACTOR)
        run(["xcrun", "clang", "-fobjc-arc", "-framework", "Foundation", "-framework", "CoreGraphics",
             "-framework", "ImageIO", source, "-o", binary], "clang")
        renders = os.path.join(temp, "renders")
        os.mkdir(renders)
        run([binary, car, name, renders] + [a for a, _, _ in APPEARANCES], "reading the renders")

        os.makedirs(iconset, exist_ok=True)
        for stale in os.listdir(iconset):
            if stale.endswith((".png", ".jpg", ".jpeg")):
                os.remove(os.path.join(iconset, stale))
        images = []
        for appearance, filename, appearances in APPEARANCES:
            png = os.path.join(renders, f"{appearance}.png")
            if not os.path.isfile(png):
                fail(f"no {appearance} render", 65)
            if not opaque(png):
                fail(f"the {appearance} render is not opaque", 65)
            jpeg = os.path.join(iconset, filename)
            psnr = encode(png, jpeg, args.quality)
            print(f"{filename}: {os.path.getsize(png)} -> {os.path.getsize(jpeg)} bytes, PSNR {psnr} dB")
            entry = {"filename": filename, "idiom": "universal", "platform": "ios", "size": "1024x1024"}
            if appearances:
                entry = {"appearances": appearances, **entry}
            images.append(entry)

    with open(os.path.join(iconset, "Contents.json"), "w") as handle:
        # Xcode's own layout, so a re-render diffs as its images only.
        json.dump({"images": images, "info": {"author": "xcode", "version": 1}}, handle,
                  indent=2, separators=(",", " : "))
        handle.write("\n")
    print(f"wrote {iconset}")


if __name__ == "__main__":
    main()
