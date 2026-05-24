# -*- coding: utf-8 -*-
"""Ad-hoc verification of langdetect behaviour with Chinese text.

Variant 1 — length sensitivity (Simplified Chinese repeated at n=20/50/100/200):
    Tests how detection probability changes as the input grows.

Variant 2 — HK prospectus Traditional Chinese block:
    Tests a realistic Traditional Chinese IPO prospectus excerpt.

Variant 3 — Simplified vs Traditional side-by-side:
    Confirms langdetect correctly distinguishes zh-cn from zh-tw.

Usage
-----
    python scripts/dev/verify_chinese_handling.py            # run all variants
    python scripts/dev/verify_chinese_handling.py --variant 1
    python scripts/dev/verify_chinese_handling.py --variant 2
    python scripts/dev/verify_chinese_handling.py --variant 3
    python scripts/dev/verify_chinese_handling.py --help
"""
import argparse
import sys

sys.stdout.reconfigure(encoding="utf-8")


def _require_langdetect():
    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0
        return detect_langs
    except ImportError:
        sys.exit("langdetect is not installed.  Run: pip install langdetect")


def variant1(detect_langs) -> None:
    """Length sensitivity: Simplified Chinese at different repetition counts."""
    print("=== Variant 1: Length sensitivity (Simplified Chinese) ===")
    base = "本集团拟将全球发售所得款项净额用于以下用途。"
    for n in [20, 50, 100, 200]:
        text = base * n
        snippet = text[:5000]
        langs = detect_langs(snippet)
        print(
            f"  n={n:3d}  len={len(snippet):4d}  "
            f"langs={[(str(l.lang), round(float(l.prob), 4)) for l in langs]}"
        )


def variant2(detect_langs) -> None:
    """Realistic HK prospectus Traditional Chinese block."""
    print("=== Variant 2: HK prospectus Traditional Chinese ===")
    text = (
        "本集團擬將全球發售所得款項淨額用於以下用途。"
        "董事會認為，全球發售乃本公司擴大股東基礎及提升本集團知名度之良機。"
        "我們計劃將所得款項淨額約百分之四十五用於研發。"
        "約百分之三十五用於擴大海外市場業務及銷售網絡。"
        "約百分之十用於償還銀行貸款及其他借款。"
        "餘下約百分之十將用作營運資金及其他一般公司用途。"
        "本次發售所得款項淨額的實際用途將取決於本集團的業務需求及市場狀況。"
        "本集團將審慎管理所得款項，以確保股東獲得最大回報。"
        "有關所得款項用途的進一步詳情，請參閱本招股章程其他章節。"
    ) * 8
    snippet = text[:5000]
    langs = detect_langs(snippet)
    print(f"  Text length : {len(text)}")
    print(f"  Snippet len : {len(snippet)}")
    print(f"  langs       : {[(str(l.lang), round(float(l.prob), 4)) for l in langs]}")


def variant3(detect_langs) -> None:
    """Simplified vs Traditional Chinese side-by-side."""
    print("=== Variant 3: Simplified vs Traditional Chinese ===")

    text_sc = (
        "今天的天气非常好，我们一起去公园散步吧。"
        "中国是一个有着悠久历史和丰富文化的国家。"
        "人工智能技术正在改变我们的生活方式。"
        "学校明天将举行一年一度的运动会。"
        "这本书讲述了一个关于勇气和友谊的故事。"
    ) * 10
    print(f"  Simplified Chinese — length: {len(text_sc)}")
    langs_sc = detect_langs(text_sc[:5000])
    print(f"  langs: {[(str(l.lang), round(float(l.prob), 4)) for l in langs_sc]}")

    text_tc = (
        "本集團擬將全球發售所得款項淨額用於以下用途。"
        "董事會認為，全球發售乃本公司擴大股東基礎及提升本集團知名度之良機。"
        "我們計劃將所得款項淨額約百分之四十五用於研發。"
    ) * 20
    print(f"\n  Traditional Chinese — length: {len(text_tc)}")
    langs_tc = detect_langs(text_tc[:5000])
    print(f"  langs: {[(str(l.lang), round(float(l.prob), 4)) for l in langs_tc]}")


VARIANTS = {1: variant1, 2: variant2, 3: variant3}


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--variant",
        type=int,
        choices=[1, 2, 3],
        default=None,
        metavar="{1,2,3}",
        help="Which variant to run (default: all).",
    )
    args = parser.parse_args()

    detect_langs = _require_langdetect()

    if args.variant is None:
        for fn in VARIANTS.values():
            fn(detect_langs)
            print()
    else:
        VARIANTS[args.variant](detect_langs)


if __name__ == "__main__":
    main()
