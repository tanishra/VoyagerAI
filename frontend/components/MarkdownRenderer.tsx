import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div
      className="
        text-sm max-w-none
        [&_p]:my-1.5 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0
        [&_ul]:my-1.5 [&_ol]:my-1.5
        [&_li]:my-0.5 [&_li]:ml-1
        [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2
        [&_strong]:font-semibold [&_em]:italic
        [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono
        [&_pre]:bg-muted [&_pre]:p-3 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_pre]:my-2
        [&_pre_code]:bg-transparent [&_pre_code]:p-0
        [&_blockquote]:border-l-2 [&_blockquote]:border-border [&_blockquote]:pl-3 [&_blockquote]:text-muted-foreground [&_blockquote]:my-2
        [&_h1]:text-base [&_h1]:font-semibold [&_h1]:my-2
        [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:my-2
        [&_h3]:text-sm [&_h3]:font-medium [&_h3]:my-1.5
        [&_hr]:border-border [&_hr]:my-3
        [&_table]:w-full [&_table]:my-2 [&_table]:text-xs
        [&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-1 [&_th]:font-medium [&_th]:text-left [&_th]:bg-muted
        [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1
      "
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer">
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
