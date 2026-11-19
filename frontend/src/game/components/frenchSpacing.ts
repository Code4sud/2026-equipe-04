/**
 * Espaces insécables du français, ajoutés à l'affichage : « ? », « ! », « : », « ; » et les
 * guillemets ne se retrouvent jamais seuls en début de ligne. Les textes sources restent simples.
 */
export function frenchSpacing(text: string) {
  return text.replace(/ ([?!:;»])/g, ' $1').replace(/« /g, '« ');
}
