import type { PropsWithChildren } from 'react'

export function DesktopGuard({ children }: PropsWithChildren) {
  return (
    <>
      <div className="desktop-only-notice">
        <span className="seal">观</span>
        <h1>请使用桌面浏览器</h1>
        <p>群雄夜宴为 1280px 以上观战大屏设计。</p>
      </div>
      <div className="desktop-app">{children}</div>
    </>
  )
}
