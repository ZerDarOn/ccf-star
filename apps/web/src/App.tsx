const players = [
  { name: "林风眠", role: "GM", color: "#d7b56d" },
  { name: "苏鸣澈", role: "PC 1", color: "#8ea8c8" },
  { name: "白栀", role: "PC 2", color: "#bca9d6" },
];

const messages = [
  { author: "林风眠", text: "你们在雨夜抵达了旧车站。", time: "21:32" },
  { author: "苏鸣澈", text: "我先观察站台附近有没有人。", time: "21:33" },
  { author: "白栀", text: "1d100 → 42 / 60 成功", time: "21:33" },
];

export function App() {
  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">COC-STAR / ROOM</span>
          <h1>旧车站调查</h1>
        </div>
        <div className="connection-status"><span className="status-dot" />初始化工作台</div>
      </header>
      <section className="workspace">
        <aside className="sidebar">
          <div className="panel-heading"><span>房间成员</span><span className="muted">3 / 8</span></div>
          <div className="player-list">
            {players.map((player) => (
              <div className="player" key={player.name}>
                <span className="avatar" style={{ background: player.color }}>{player.name.slice(0, 1)}</span>
                <span><strong>{player.name}</strong><small>{player.role}</small></span>
              </div>
            ))}
          </div>
          <div className="sidebar-note"><span>下一步</span><p>创建第一个场景与角色棋子</p></div>
        </aside>
        <section className="board-area">
          <div className="board-toolbar">
            <span className="toolbar-title">场景 01 · 旧车站月台</span>
            <div className="toolbar-actions"><button type="button">场景</button><button type="button">资源</button><button type="button">保存</button></div>
          </div>
          <div className="board">
            <div className="board-grid" /><div className="board-location">旧车站 · 23:48</div>
            <div className="token token-gm">林</div><div className="token token-pc-one">苏</div><div className="token token-pc-two">白</div>
            <div className="board-empty-state"><span className="empty-icon">✦</span><strong>虚拟桌面准备就绪</strong><p>未来这里将承载地图、角色、面板和场景演出</p></div>
          </div>
        </section>
        <aside className="chat-panel">
          <div className="panel-heading"><span>主频道</span><span className="muted">聊天</span></div>
          <div className="message-list">
            {messages.map((message) => (
              <article className="message" key={`${message.author}-${message.time}`}>
                <div className="message-meta"><strong>{message.author}</strong><time>{message.time}</time></div><p>{message.text}</p>
              </article>
            ))}
          </div>
          <div className="chat-composer"><span>苏鸣澈</span><div className="composer-input">输入消息……</div><button type="button">发送</button></div>
        </aside>
      </section>
    </main>
  );
}

