/** Affiche un message en surlignant l'extrait d'où vient un talent. */
export function Highlight({ text, quote }: { text: string; quote?: string }) {
  const start = quote ? text.indexOf(quote) : -1;
  if (!quote || start === -1) return <>{text}</>;
  return (
    <>
      {text.slice(0, start)}
      <mark>{quote}</mark>
      {text.slice(start + quote.length)}
    </>
  );
}
