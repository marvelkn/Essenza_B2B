import manifest from '../assets/metadata/v7_model_manifest.json';
import { loadFeatureApiUrl } from './featureApiConfig';

let operation = Promise.resolve();
let sequence = 0;

export class PredictionError extends Error {
  constructor(code, message) {
    super(message);
    this.name = 'PredictionError';
    this.code = code;
  }
}

function cancelled(signal) {
  if (signal?.aborted) {
    throw new PredictionError('CANCELLED', 'Analisis dibatalkan.');
  }
}

function assertPrediction(payload) {
  const scores = payload?.scores;
  if (
    payload?.status !== 'ok' ||
    payload?.runtime !== 'lightgbm' ||
    payload?.model_id !== manifest.model_id ||
    payload?.bundle_id !== manifest.bundle_id ||
    payload?.feature_schema_id !== manifest.feature_schema_id ||
    payload?.primary_threshold !== manifest.primary_threshold ||
    payload?.label_count !== manifest.labels.length ||
    payload?.input_dimensions !== manifest.feature_spec.dimensions.input ||
    !Array.isArray(scores) || scores.length !== manifest.labels.length ||
    scores.some((item, index) => item?.label !== manifest.labels[index] ||
      typeof item.score !== 'number' || !Number.isFinite(item.score) ||
      item.score < 0 || item.score > 1) ||
    typeof payload.smiles !== 'string' ||
    !payload.smiles.trim() ||
    !(payload.compound_name == null || typeof payload.compound_name === 'string')
  ) {
    throw new PredictionError(
      'PREDICTION_SCHEMA_MISMATCH',
      'Layanan analisis belum cocok dengan aplikasi ini. Hubungi pengelola.',
    );
  }
}

async function fetchPrediction(smiles, compoundName, signal) {
  const baseUrl = await loadFeatureApiUrl();
  if (!baseUrl) {
    throw new PredictionError('API_NOT_CONFIGURED', 'Koneksi analisis belum diatur. Buka Panduan atau hubungi pengelola.');
  }
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort);
  const timeout = setTimeout(abort, 20000);
  try {
    cancelled(signal);
    const response = await fetch(`${baseUrl}/predict`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        smiles: smiles || null,
        compound_name: compoundName || null,
        feature_schema_id: manifest.feature_schema_id,
        bundle_id: manifest.bundle_id,
      }),
      signal: controller.signal,
    });
    const payload = await response.json();
    cancelled(signal);
    if (!response.ok) {
      const detail = payload?.detail;
      throw new PredictionError(
        detail?.code || 'PREDICTION_API_ERROR',
        detail?.message || 'Senyawa ini belum bisa diproses. Coba pilihan lain.',
      );
    }
    assertPrediction(payload);
    return payload;
  } catch (error) {
    if (signal?.aborted) {
      throw new PredictionError('CANCELLED', 'Analisis dibatalkan.');
    }
    if (error instanceof PredictionError) {
      throw error;
    }
    throw new PredictionError(
      'NETWORK',
      controller.signal.aborted
        ? 'Layanan analisis terlalu lama merespons. Coba lagi.'
        : 'Layanan analisis tidak terhubung. Periksa koneksi atau hubungi pengelola.',
    );
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}

async function resolve({ query, signal }) {
  const baseUrl = await loadFeatureApiUrl();
  if (!baseUrl) {
    throw new PredictionError('API_NOT_CONFIGURED', 'Koneksi analisis belum diatur. Buka Panduan atau hubungi pengelola.');
  }
  const controller = new AbortController();
  const abort = () => controller.abort();
  signal?.addEventListener('abort', abort);
  const timeout = setTimeout(abort, 20000);
  try {
    cancelled(signal);
    const response = await fetch(`${baseUrl}/resolve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: query.trim() }),
      signal: controller.signal,
    });
    const payload = await response.json();
    cancelled(signal);
    if (!response.ok) {
      const detail = payload?.detail;
      throw new PredictionError(detail?.code || 'RESOLVE_ERROR',
        detail?.message || 'Senyawa belum ditemukan. Coba nama atau rumus lain.');
    }
    if (!Array.isArray(payload?.candidates) || !payload.candidates.length ||
      payload.candidates.some(item => typeof item?.name !== 'string' ||
        typeof item?.smiles !== 'string' || !item.smiles ||
        typeof item?.molecular_formula !== 'string' ||
        typeof item?.in_catalog !== 'boolean' || typeof item?.prediction_supported !== 'boolean')) {
      throw new PredictionError('RESOLVE_ERROR', 'Respons pencarian senyawa tidak valid.');
    }
    return payload.candidates;
  } catch (error) {
    if (signal?.aborted) {
      throw new PredictionError('CANCELLED', 'Pencarian dibatalkan.');
    }
    if (error instanceof PredictionError) {
      throw error;
    }
    throw new PredictionError('NETWORK', controller.signal.aborted
      ? 'Pencarian terlalu lama. Coba lagi.'
      : 'Layanan pencarian tidak terhubung. Periksa koneksi atau hubungi pengelola.');
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', abort);
  }
}

async function predict({ smiles = '', compoundName = '', catalogName = '', sampleName = '', signal, onProgress }) {
  cancelled(signal);
  onProgress?.(0, manifest.labels.length);
  const payload = await fetchPrediction(smiles.trim(), compoundName.trim(), signal);
  cancelled(signal);
  const scores = payload.scores.map(({ label, score }) => ({ label, score }));
  onProgress?.(manifest.labels.length, manifest.labels.length);
  const labels = scores.filter(item => item.score >= manifest.primary_threshold)
    .sort((a, b) => b.score - a.score || a.label.localeCompare(b.label));
  sequence += 1;
  return {
    id: `v7-${Date.now()}-${sequence}`,
    sampleName: (sampleName.trim() || payload.compound_name || 'Sampel molekul').slice(0, 80),
    inputName: (catalogName.trim() || compoundName.trim()).slice(0, 200) || null,
    inputSmiles: smiles.trim() || payload.smiles,
    canonicalSmiles: payload.smiles,
    createdAt: new Date().toISOString(),
    demo: false,
    modelId: manifest.model_id,
    bundleId: manifest.bundle_id,
    structureValidated: true,
    labels,
    scores,
  };
}

export const v7PredictionService = {
  resolve,
  predict(args) {
    const next = operation.then(() => predict(args), () => predict(args));
    operation = next.catch(() => undefined);
    return next;
  },
};
