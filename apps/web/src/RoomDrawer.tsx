import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";

export interface RoomDrawerProps {
  children: ReactNode;
  onClose: () => void;
  open: boolean;
  title: string;
}

export function RoomDrawer({ children, onClose, open, title }: RoomDrawerProps) {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [size, setSize] = useState({ height: 680, width: 440 });
  const dragRef = useRef<{ originX: number; originY: number; x: number; y: number } | null>(null);
  const resizeRef = useRef<{ originX: number; originY: number; height: number; width: number } | null>(null);

  useEffect(() => {
    if (!open) return;
    setPosition({ x: 0, y: 0 });
    setSize({ height: Math.min(window.innerHeight - 100, 760), width: Math.min(window.innerWidth - 24, 440) });
  }, [open]);

  useEffect(() => {
    const handlePointerMove = (event: globalThis.PointerEvent) => {
      if (dragRef.current) {
        setPosition({ x: dragRef.current.x + event.clientX - dragRef.current.originX, y: dragRef.current.y + event.clientY - dragRef.current.originY });
      }
      if (resizeRef.current) {
        setSize({ width: Math.max(320, resizeRef.current.width + event.clientX - resizeRef.current.originX), height: Math.max(360, resizeRef.current.height + event.clientY - resizeRef.current.originY) });
      }
    };
    const handlePointerUp = () => { dragRef.current = null; resizeRef.current = null; };
    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
    return () => { window.removeEventListener("pointermove", handlePointerMove); window.removeEventListener("pointerup", handlePointerUp); };
  }, []);

  if (!open) return null;

  const handleDragStart = (event: PointerEvent<HTMLDivElement>) => {
    dragRef.current = { originX: event.clientX, originY: event.clientY, x: position.x, y: position.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const handleResizeStart = (event: PointerEvent<HTMLDivElement>) => {
    resizeRef.current = { originX: event.clientX, originY: event.clientY, height: size.height, width: size.width };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  return <aside className="room-drawer" role="dialog" aria-modal="false" aria-label={title} style={{ width: size.width, height: size.height, transform: `translate(${position.x}px, ${position.y}px)` }}>
    <header className="room-drawer-header" onPointerDown={handleDragStart}><div><span className="eyebrow">工作台工具 · 可移动窗口</span><h2>{title}</h2></div><button type="button" className="drawer-close" onPointerDown={(event) => event.stopPropagation()} onClick={onClose} aria-label={`关闭${title}`}>×</button></header>
    <div className="room-drawer-content">{children}</div>
    <div className="room-drawer-resize" onPointerDown={handleResizeStart} role="presentation" aria-hidden="true" />
  </aside>;
}
