import type { Attachment } from "../types";
import "./chat.css";

export function ChatFiles({ files }: { files: Attachment[] }) {
  if (!files?.length) return null;
  return (
    <ul className="attachments chat-files" aria-label="Message attachments">
      {files.map((file) => (
        <li key={file.id}>
          {file.preview_url && (
            <a href={file.url} target="_blank" rel="noopener">
              <img src={file.preview_url} alt={file.display_name} loading="lazy" />
            </a>
          )}
          <a href={file.url}>{file.display_name}</a>
          <span className="chat__meta"> · {Math.ceil(file.size / 1024)} KiB</span>
        </li>
      ))}
    </ul>
  );
}
