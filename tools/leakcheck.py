#!/usr/bin/env python3
"""この文書に固有名詞・パス・ポート・連絡先が混じっていないかを見る。

使い方:
    python3 tools/leakcheck.py                      B と C を見る
    python3 tools/leakcheck.py --words <ファイル>    A も見る（1 行 1 語）

3 本立て:
    A 語のリスト   … 知っている名前。★リポジトリの外から読む
                     （リスト自体を中に置くと、それが固有名詞の一覧になる）
    B パターン     … 知らない名前も拾う形。A だけでは、知っている語しか見ない
    C 陽性対照     … わざと混ぜた見本で落ちることを確かめる
                     （本文が 0 件のとき、検査が壊れていても緑になるため）

この検査が緑でも守られていないもの:
    - 日本語の固有名詞（会社名・人名）は、A の語リストを渡さない限り見ていない
    - 文脈だけで分かる情報（「あの案件」「先日の障害」）は、どの形でも見ていない
    - 画像・図の中の文字は見ていない
"""

import argparse
import hashlib
import pathlib
import re
import sys

# 走査する対象。ここに無いファイルは見ていない。
対象 = ["CLAUDE.md", "README.md"]

# B のパターン。知らない名前も拾うための形。
パターン = [
    ("ドライブ文字のパス", re.compile(r"\b[A-Za-z]:[\\/]")),
    ("ホームのパス", re.compile(r"/(?:home|Users)/[A-Za-z0-9._-]+")),
    ("ポートらしい数", re.compile(r":\d{4,5}\b")),
    ("連絡先らしいもの", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("URL", re.compile(r"https?://\S+")),
    ("ホスト名らしいもの", re.compile(r"\b[a-z0-9-]+\.(?:com|net|org|jp|io|dev|co\.jp)\b")),
    ("IP らしいもの", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")),
]


def 走査(text, 語):
    """当たった (種類, 行番号, 抜粋) を返す。"""
    出 = []
    for n, line in enumerate(text.splitlines(), 1):
        for 名, pat in パターン:
            for m in pat.finditer(line):
                出.append((名, n, m.group(0)[:60]))
        for w in 語:
            if w and w in line:
                # 語そのものは出さない。どの語かは照合した人が手元のリストで引く。
                h = hashlib.sha256(w.encode("utf-8")).hexdigest()[:8]
                出.append(("語のリスト(%s)" % h, n, "（語は出しません）"))
    return 出


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--words", help="語のリスト（1 行 1 語）。リポジトリの外に置く")
    ap.add_argument("--fixture", default="tests/fixture_should_fail.md",
                    help="陽性対照の見本")
    args = ap.parse_args()

    語 = []
    語の出どころ = "★渡されていません（A は走っていません）"
    if args.words:
        p = pathlib.Path(args.words)
        if not p.exists():
            print("★語のリストが見つかりません: %s" % p)
            return 2
        語 = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
              if ln.strip() and not ln.startswith("#")]
        語の出どころ = "%s（%d 語）" % (p, len(語))

    # ---- C 陽性対照。先に見る。ここが落ちないなら、以降の緑は根拠を持たない。
    fx = pathlib.Path(args.fixture)
    if not fx.exists():
        print("★陽性対照の見本が在りません: %s" % fx)
        print("  ⇒ 見本が無いと、検査が壊れていても本文 0 件で緑になります。")
        return 2
    当たり = 走査(fx.read_text(encoding="utf-8"), 語)
    if not 当たり:
        print("★★陽性対照が落ちません（見本 %s に 1 件も当たらない）" % fx)
        print("  ⇒ 検査そのものが壊れています。以降の『0 件』は根拠を持ちません。")
        return 2
    print("陽性対照: %s で %d 件 当たりました（検査は生きています）" % (fx, len(当たり)))
    print("  当たった種類: %s" % ", ".join(sorted({t for t, _, _ in 当たり})))
    print()

    # ---- A と B。本文を見る。
    print("語のリスト: %s" % 語の出どころ)
    print("走査した対象: %s" % ", ".join(対象))
    行数 = 0
    見つからない = []
    全部 = []
    for name in 対象:
        p = pathlib.Path(name)
        if not p.exists():
            見つからない.append(name)
            continue
        text = p.read_text(encoding="utf-8")
        行数 += len(text.splitlines())
        for t, n, s in 走査(text, 語):
            全部.append((name, t, n, s))
    print("走査した行: %d 行 / 見つからなかった対象: %d 件%s"
          % (行数, len(見つからない),
             ("（%s）" % ", ".join(見つからない)) if 見つからない else ""))
    print()

    if 全部:
        print("★当たりました: %d 件" % len(全部))
        for name, t, n, s in 全部:
            print("  %s:%d  %s  %s" % (name, n, t, s))
        print()
        print("  ⇒ 固有名詞・パス・ポート・連絡先は、環境ごとの値として知識ベース側へ。")
        return 1

    print("当たりませんでした: 0 件（%d 行を見て）" % 行数)
    print()
    print("★この検査が見ていないもの:")
    if not 語:
        print("  - 日本語の固有名詞（会社名・人名）。A の語リストを渡していません")
    print("  - 文脈だけで分かる情報（「あの案件」「先日の障害」）は、どの形でも見ていません")
    print("  - 画像・図の中の文字は見ていません")
    print("  - 走査しているのは上の対象だけです。足したファイルは、ここに書くまで見ていません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
