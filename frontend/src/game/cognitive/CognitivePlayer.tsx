/** Point d'entrée des jeux chronométrés : à remplacer par le lot « jeux cognitifs ». */
export function CognitivePlayer({ instrumentId }: { instrumentId: string }) {
  return <p className="state">Jeu « {instrumentId} » bientôt disponible.</p>;
}
