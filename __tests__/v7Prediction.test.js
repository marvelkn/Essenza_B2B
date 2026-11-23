import AsyncStorage from '@react-native-async-storage/async-storage';
import catalog from '../src/assets/catalog/compounds.json';
import manifest from '../src/assets/metadata/v7_model_manifest.json';
import { isAnalysis } from '../src/domain/analysis';
import { v7PredictionService } from '../src/services/v7Prediction';
import { HISTORY_KEY, readHistory, writeHistory } from '../src/storage/history';

jest.mock('../src/services/featureApiConfig', () => ({ loadFeatureApiUrl: async () => 'http://127.0.0.1:8000' }));
const originalFetch = global.fetch;
const scores = () => manifest.labels.map((label, index) => ({ label, score: index ? 0.1 : 0.8 }));
const payload = () => ({
  status: 'ok', runtime: 'lightgbm', model_id: manifest.model_id,
  bundle_id: manifest.bundle_id, feature_schema_id: manifest.feature_schema_id,
  primary_threshold: manifest.primary_threshold, label_count: 109, input_dimensions: 2056,
  smiles: 'CCO', scores: scores(),
});

beforeEach(() => {
  jest.clearAllMocks();
  global.fetch = jest.fn(async () => ({ ok: true, json: async () => payload() }));
});
afterEach(() => { global.fetch = originalFetch; });

test('predicts from the local API without a native inference module or feature transport', async () => {
  const result = await v7PredictionService.predict({ smiles: ' CCO ', catalogName: 'Ethanol' });
  expect(global.fetch).toHaveBeenCalledTimes(1);
  expect(global.fetch).toHaveBeenCalledWith('http://127.0.0.1:8000/predict', expect.objectContaining({ method: 'POST' }));
  expect(JSON.parse(global.fetch.mock.calls[0][1].body)).toEqual({
    smiles: 'CCO', compound_name: null, feature_schema_id: manifest.feature_schema_id,
    bundle_id: manifest.bundle_id,
  });
  expect(result.scores).toEqual(scores());
  expect(result.labels).toEqual([{ label: manifest.labels[0], score: 0.8 }]);
  expect(result.demo).toBe(false);
  expect(result.bundleId).toBe(manifest.bundle_id);
  expect(isAnalysis(result)).toBe(true);
});

test('a real catalog compound with a long name can be saved and reopened in history', async () => {
  const compound = catalog.compounds.find(item => item.id === 6581);
  expect(compound.name.length).toBeGreaterThan(200);
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ ...payload(), smiles: compound.smiles }) });
  const result = await v7PredictionService.predict({
    smiles: compound.smiles, catalogName: compound.name, sampleName: compound.name,
  });
  expect(result.sampleName).toBe(compound.name.slice(0, 80));
  expect(result.inputName).toBe(compound.name.slice(0, 200));
  expect(result.canonicalSmiles).toBe(compound.smiles);
  expect(isAnalysis(result)).toBe(true);
  await writeHistory([result]);
  const raw = AsyncStorage.setItem.mock.calls[0][1];
  expect(AsyncStorage.setItem).toHaveBeenCalledWith(HISTORY_KEY, raw);
  AsyncStorage.getItem.mockResolvedValueOnce(raw);
  expect(await readHistory()).toEqual([result]);
});

test('the API name fallback respects the sample-name limit without truncating the request', async () => {
  const compoundName = 'Nama senyawa panjang '.repeat(7).trim();
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ ...payload(), compound_name: compoundName }) });
  const result = await v7PredictionService.predict({ compoundName });
  expect(JSON.parse(global.fetch.mock.calls[0][1].body).compound_name).toBe(compoundName);
  expect(result.sampleName).toBe(compoundName.slice(0, 80));
  expect(result.inputName).toBe(compoundName);
  expect(isAnalysis(result)).toBe(true);
});

test.each([
  ['runtime', { runtime: 'another-runtime' }],
  ['model', { model_id: 'wrong' }],
  ['bundle', { bundle_id: 'wrong' }],
  ['feature schema', { feature_schema_id: 'wrong' }],
  ['threshold', { primary_threshold: 0.4 }],
  ['label count', { label_count: 108 }],
  ['input dimensions', { input_dimensions: 2048 }],
  ['missing structure', { smiles: '' }],
  ['missing scores', { scores: undefined }],
  ['features without predictions', { scores: undefined, fingerprint: Array(2056).fill(0) }],
])('rejects a mismatched prediction contract: %s', async (_, override) => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ ...payload(), ...override }) });
  await expect(v7PredictionService.predict({ smiles: 'CCO' }))
    .rejects.toMatchObject({ code: 'PREDICTION_SCHEMA_MISMATCH' });
});

test.each([
  ['missing label', values => values.slice(1)],
  ['additional label', values => [...values, { label: 'extra', score: 0.1 }]],
  ['reordered labels', values => [values[1], values[0], ...values.slice(2)]],
  ['unknown label', values => [{ ...values[0], label: 'unknown' }, ...values.slice(1)]],
  ['duplicate label', values => [values[1], ...values.slice(1)]],
  ['negative score', values => [{ ...values[0], score: -0.1 }, ...values.slice(1)]],
  ['score above one', values => [{ ...values[0], score: 1.1 }, ...values.slice(1)]],
  ['non-finite score', values => [{ ...values[0], score: Infinity }, ...values.slice(1)]],
  ['NaN score', values => [{ ...values[0], score: NaN }, ...values.slice(1)]],
  ['string score', values => [{ ...values[0], score: '0.8' }, ...values.slice(1)]],
  ['null score entry', values => [null, ...values.slice(1)]],
])('never returns a malformed or partial prediction: %s', async (_, change) => {
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ ...payload(), scores: change(scores()) }) });
  await expect(v7PredictionService.predict({ smiles: 'CCO' }))
    .rejects.toMatchObject({ code: 'PREDICTION_SCHEMA_MISMATCH' });
});

test('selects all scores at or above the unchanged threshold and sorts the visible labels', async () => {
  const values = scores();
  values[0].score = 0.5;
  values[1].score = 0.9;
  values[2].score = 0.499999;
  global.fetch.mockResolvedValue({ ok: true, json: async () => ({ ...payload(), scores: values }) });
  const result = await v7PredictionService.predict({ smiles: 'CCO' });
  expect(result.scores).toEqual(values);
  expect(result.labels).toEqual([values[1], values[0]]);
});

test('surfaces API eligibility errors without fabricating a result', async () => {
  global.fetch.mockResolvedValue({ ok: false, json: async () => ({ detail: {
    code: 'UNSUPPORTED_COMPOUND', message: 'Senyawa ini di luar cakupan prediksi aroma bahan parfum.',
  } }) });
  await expect(v7PredictionService.predict({ smiles: 'O' })).rejects.toMatchObject({ code: 'UNSUPPORTED_COMPOUND' });
});

test('an offline API produces an actionable error', async () => {
  global.fetch.mockRejectedValue(new TypeError('Network request failed'));
  await expect(v7PredictionService.predict({ smiles: 'CCO' })).rejects.toMatchObject({ code: 'NETWORK' });
});

test('a cancelled request is not sent', async () => {
  const controller = new AbortController();
  controller.abort();
  await expect(v7PredictionService.predict({ smiles: 'CCO', signal: controller.signal })).rejects.toMatchObject({ code: 'CANCELLED' });
  expect(global.fetch).not.toHaveBeenCalled();
});

test('a late response after cancellation is discarded and does not block the next request', async () => {
  let finish;
  let requestSent;
  const started = new Promise(resolve => { requestSent = resolve; });
  global.fetch.mockImplementationOnce(() => new Promise(resolve => {
    finish = resolve;
    requestSent();
  }));
  const controller = new AbortController();
  const pending = v7PredictionService.predict({ smiles: 'CCO', signal: controller.signal });
  const settled = pending.then(() => null, error => error);
  await started;
  controller.abort();
  finish({ ok: true, json: async () => payload() });
  expect(await settled).toMatchObject({ code: 'CANCELLED' });
  await expect(v7PredictionService.predict({ smiles: 'CCO' })).resolves.toMatchObject({ canonicalSmiles: 'CCO' });
});
