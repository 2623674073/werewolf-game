export interface CharacterAsset {
  slug: string
  accent: string
}

export const characterAssets: Record<string, CharacterAsset> = {
  刘备: { slug: 'liu-bei', accent: '#d7b35d' },
  关羽: { slug: 'guan-yu', accent: '#b3423e' },
  张飞: { slug: 'zhang-fei', accent: '#9a718a' },
  诸葛亮: { slug: 'zhuge-liang', accent: '#73a9a5' },
  赵云: { slug: 'zhao-yun', accent: '#b9c7cf' },
  曹操: { slug: 'cao-cao', accent: '#8e4a45' },
  司马懿: { slug: 'sima-yi', accent: '#75648d' },
  典韦: { slug: 'dian-wei', accent: '#9b6d4a' },
  许褚: { slug: 'xu-chu', accent: '#b27d52' },
  夏侯惇: { slug: 'xiahou-dun', accent: '#8f3732' },
  孙权: { slug: 'sun-quan', accent: '#6f9b8d' },
  周瑜: { slug: 'zhou-yu', accent: '#ad6f69' },
  陆逊: { slug: 'lu-xun', accent: '#c38b64' },
  甘宁: { slug: 'gan-ning', accent: '#547f99' },
  太史慈: { slug: 'taishi-ci', accent: '#858c9d' },
  吕布: { slug: 'lu-bu', accent: '#b63632' },
  貂蝉: { slug: 'diao-chan', accent: '#b97f99' },
  董卓: { slug: 'dong-zhuo', accent: '#755548' },
  袁绍: { slug: 'yuan-shao', accent: '#ba9957' },
  袁术: { slug: 'yuan-shu', accent: '#a88345' },
}

export function portraitFor(character: string): string {
  const slug = characterAssets[character]?.slug ?? 'fallback'
  return `/portraits/${slug}.webp`
}

export const roleTheme: Record<string, { mark: string; color: string; label: string }> = {
  狼人: { mark: '狼', color: '#cf4c49', label: '潜伏者' },
  预言家: { mark: '卜', color: '#64b8c2', label: '洞察者' },
  女巫: { mark: '药', color: '#a67ac1', label: '司药者' },
  猎人: { mark: '弓', color: '#d59b52', label: '追猎者' },
  村民: { mark: '民', color: '#9aac9e', label: '忠良' },
}
