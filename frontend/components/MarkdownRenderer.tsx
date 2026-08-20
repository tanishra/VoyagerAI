import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MarkdownRenderer({ content }: { content: string }) {
  return (
    <div
      className="
        text-sm leading-relaxed max-w-none
        [&_p]:my-2 [&_p:first-child]:mt-0 [&_p:last-child]:mb-0
        [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5
        [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5
        [&_li]:my-0.5
        [&_a]:text-primary [&_a]:underline [&_a]:underline-offset-2 [&_a]:hover:text-primary/80
        [&_strong]:font-semibold [&_em]:italic
        [&_code]:bg-muted [&_code]:px-1.5 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_code]:font-mono [&_code]:text-primary
        [&_pre]:bg-muted [&_pre]:p-3.5 [&_pre]:rounded-lg [&_pre]:overflow-x-auto [&_pre]:my-2.5 [&_pre]:text-xs
        [&_pre_code]:bg-transparent [&_pre_code]:p-0 [&_pre_code]:text-foreground
        [&_blockquote]:border-l-2 [&_blockquote]:border-primary/30 [&_blockquote]:pl-3.5 [&_blockquote]:text-muted-foreground [&_blockquote]:my-2.5 [&_blockquote]:italic
        [&_h1]:text-lg [&_h1]:font-semibold [&_h1]:my-3 [&_h1]:text-foreground
        [&_h2]:text-base [&_h2]:font-semibold [&_h2]:my-2.5 [&_h2]:text-foreground
        [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:my-2 [&_h3]:text-foreground
        [&_h4]:text-sm [&_h4]:font-medium [&_h4]:my-1.5
        [&_hr]:border-border [&_hr]:my-4
        [&_table]:w-full [&_table]:my-3 [&_table]:text-xs [&_table]:border-collapse
        [&_th]:border [&_th]:border-border [&_th]:px-3 [&_th]:py-1.5 [&_th]:font-semibold [&_th]:text-left [&_th]:bg-muted
        [&_td]:border [&_td]:border-border [&_td]:px-3 [&_td]:py-1.5
        [&_tr:hover]:bg-muted/30
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
