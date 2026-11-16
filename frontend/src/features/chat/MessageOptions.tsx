type Props = {
  canContribute: boolean;
  onReply: () => void;
  onReact: (reaction: string) => void;
  onThread: () => void;
  onShare: () => void;
  onTask: () => void;
};

/** Reading threads and task work remain available when chat contribution is restricted. */
export function MessageOptions({ canContribute, onReply, onReact, onThread, onShare, onTask }: Props) {
  return (
    <div className="chat-bubble__actions-menu">
      {canContribute && (
        <>
          <button type="button" onClick={onReply}>
            ↩️ Reply
          </button>
          <button type="button" onClick={() => onReact("👍")}>
            👍 React 👍
          </button>
          <button type="button" onClick={() => onReact("❤️")}>
            ❤️ React ❤️
          </button>
        </>
      )}
      <button type="button" onClick={onThread}>
        🧵 Open thread
      </button>
      <button type="button" onClick={onShare}>
        📢 Share to noticeboard
      </button>
      <button type="button" onClick={onTask}>
        📋 Create task
      </button>
    </div>
  );
}
