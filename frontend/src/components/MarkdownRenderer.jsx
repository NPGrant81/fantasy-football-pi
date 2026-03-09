/* ignore-breakpoints */
import ReactMarkdown from 'react-markdown';
import MermaidDiagram from './MermaidDiagram';
import { textColors } from '../utils/uiHelpers';

function CodeBlock({ className, children, ...props }) {
  const language = /language-([\w-]+)/.exec(className || '')?.[1];
  if (language === 'mermaid') {
    return <MermaidDiagram chart={String(children).trim()} />;
  }
  return (
    <code className={className} {...props}>
      {children}
    </code>
  );
}

const baseComponents = {
  strong: ({ ...props }) => (
    <span className={`font-bold ${textColors.warning}`} {...props} />
  ),
  ul: ({ ...props }) => (
    <ul className="list-disc pl-5 space-y-1 my-2" {...props} />
  ),
  li: ({ ...props }) => <li className="pl-1" {...props} />,
  code: CodeBlock,
};

export default function MarkdownRenderer({ children, components = {} }) {
  return (
    <ReactMarkdown components={{ ...baseComponents, ...components }}>
      {children}
    </ReactMarkdown>
  );
}
