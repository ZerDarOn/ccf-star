import type { FormEvent } from "react";

export interface AuthPageProps {
  errorMessage: string | null;
  mode: "login" | "register";
  password: string;
  username: string;
  onModeChange: (mode: "login" | "register") => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onUsernameChange: (value: string) => void;
}

export function AuthPage({ errorMessage, mode, password, username, onModeChange, onPasswordChange, onSubmit, onUsernameChange }: AuthPageProps) {
  const isLogin = mode === "login";

  return <main className="auth-page">
    <section className="auth-intro" aria-labelledby="auth-title">
      <span className="brand-mark">COC-STAR</span>
      <h1 id="auth-title">把跑团做成一场视觉小说。</h1>
      <p>场景、立绘、音乐与文字在同一张桌面上协作。先登录，再进入你的下一场冒险。</p>
      <div className="auth-feature-list"><span>实时房间</span><span>角色差分</span><span>场景演出</span></div>
    </section>
    <section className="auth-card" aria-labelledby="auth-form-title">
      <span className="eyebrow">进入工作台</span>
      <h2 id="auth-form-title">{isLogin ? "登录账号" : "创建账号"}</h2>
      <p>{isLogin ? "继续上一次的跑团，或加入新的房间。" : "账号仅用于保存你的房间与身份。"}</p>
      <form onSubmit={onSubmit} className="auth-form">
        <label>账号<input autoComplete="username" value={username} onChange={(event) => onUsernameChange(event.target.value)} minLength={3} maxLength={32} required /></label>
        <label>密码<input autoComplete={isLogin ? "current-password" : "new-password"} type="password" value={password} onChange={(event) => onPasswordChange(event.target.value)} minLength={8} maxLength={128} required /></label>
        {errorMessage && <p className="form-error" role="alert">{errorMessage}</p>}
        <button className="primary-action" type="submit">{isLogin ? "登录并进入首页" : "创建账号"}</button>
      </form>
      <button className="text-action" type="button" onClick={() => onModeChange(isLogin ? "register" : "login")}>{isLogin ? "还没有账号？创建一个" : "已有账号？返回登录"}</button>
    </section>
  </main>;
}
