"""Original ICND icon selectors and historically recorded consumable effects.

The original ITEM group begins at global icon 3805 (enum 8). Name-to-offset
associations below are visual matches, not recovered official item-master IDs.
Unidentified bottles deliberately retain the native empty icon selector.
"""

CONSUMABLE_SOURCE = 'https://www.wikihouse.com/toeowiki/index.php?%A5%A2%A5%A4%A5%C6%A5%E0/%BE%C3%CC%D7%C9%CA'
ITEM_ICON_BASE = 3805
ITEM_ICON_ENUM = 8
ICON_OFFSETS = {
    'アップルグミ': 0, 'オレンジグミ': 2, 'セージ': 3, 'セボリー': 4,
    'マグログミ': 5, 'レモングミ': 6, 'ベルベーヌ': 7, 'パイングミ': 8,
    'ミックスグミ': 9, 'ミラクルグミ': 10, 'ラベンダー': 12,
    'レッドセージ': 13, 'レッドセボリー': 14,
    'レッドベルベーヌ': 15, 'レッドラベンダー': 16,
}
RECOVERY = {
    'アップルグミ': (50, 0), 'レモングミ': (300, 0), 'マグログミ': (500, 0),
    'オレンジグミ': (0, 20), 'パイングミ': (0, 100),
    'ミックスグミ': (50, 20), 'ミラクルグミ': (1500, 500),
}


def icon_selector(name):
    offset = ICON_OFFSETS.get(name)
    return (0, 0) if offset is None else (ITEM_ICON_ENUM, offset)


def icon_id(name):
    kind, offset = icon_selector(name)
    return ITEM_ICON_BASE + offset if kind else 0
