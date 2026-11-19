/**
 * Poids des niveaux de preuve et seuils de confiance, tels que le serveur les applique.
 * Lus dans GET /backoffice/game/catalog ; les copies de format.ts servent tant qu'ils ne sont pas
 * chargés, si l'appel échoue ou si une ancienne version de l'API ne les envoie pas.
 */
import { createContext, useContext, useEffect, useState } from 'react';
import { gameApi } from '../api';
import type { PsyCatalog, Tier } from '../types';
import { CONFIDENCE_THRESHOLDS, TIER_WEIGHTS } from './format';

export interface Method {
  weights: Record<Tier, number>;
  thresholds: { medium: number; high: number };
}

export const FALLBACK_METHOD: Method = { weights: TIER_WEIGHTS, thresholds: CONFIDENCE_THRESHOLDS };

const isWeight = (value: unknown): value is number =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0;

/** Valeurs du catalogue ; chacune garde sa copie de secours si elle manque ou n'est pas un nombre. */
export function methodFrom(catalog: Partial<PsyCatalog> | null | undefined): Method {
  const weights = { ...TIER_WEIGHTS };
  for (const tier of Object.keys(weights) as Tier[]) {
    const value = catalog?.weights?.[tier];
    if (isWeight(value)) weights[tier] = value;
  }
  const thresholds = { ...CONFIDENCE_THRESHOLDS };
  const { medium, high } = catalog?.confidence_thresholds ?? {};
  if (isWeight(medium) && isWeight(high) && medium <= high) Object.assign(thresholds, { medium, high });
  return { weights, thresholds };
}

export const MethodContext = createContext<Method>(FALLBACK_METHOD);

export function useMethod(): Method {
  return useContext(MethodContext);
}

let shared: Promise<PsyCatalog> | null = null;

/** Le catalogue change seulement avec le contenu : chargé une fois, puis partagé entre les écrans. */
export function fetchPsyCatalog(): Promise<PsyCatalog> {
  if (!shared) {
    shared = gameApi.psyCatalog().catch((error: unknown) => {
      shared = null; // Un échec n'est pas gardé : le prochain appel réessaie.
      throw error;
    });
  }
  return shared;
}

/** Méthode du serveur pour le panneau d'un jeune ; un échec garde les copies de secours. */
export function useServerMethod(): Method {
  const [method, setMethod] = useState(FALLBACK_METHOD);
  useEffect(() => {
    let active = true;
    fetchPsyCatalog().then(
      (catalog) => {
        if (active) setMethod(methodFrom(catalog));
      },
      () => undefined,
    );
    return () => {
      active = false;
    };
  }, []);
  return method;
}
