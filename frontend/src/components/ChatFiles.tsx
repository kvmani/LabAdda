import type {Attachment} from '../types';
export function ChatFiles({files}:{files:Attachment[]}){
 if(!files?.length)return null;
 return <ul className="attachments" aria-label="Message attachments">{files.map(file=><li key={file.id}>
  {file.preview_url&&<a href={file.url} target="_blank" rel="noopener"><img src={file.preview_url} alt={file.display_name} loading="lazy"/></a>}
  <a href={file.url}>{file.display_name}</a><span className="muted small"> · {Math.ceil(file.size/1024)} KiB</span>
 </li>)}</ul>;
}
