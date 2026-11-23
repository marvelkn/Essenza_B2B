import React from 'react';
import TestRenderer, { act } from 'react-test-renderer';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import { CollectionScreen } from '../src/screens/CollectionScreen';
import { useFavorites } from '../src/storage/FavoritesProvider';
import { useLab } from '../src/storage/LabProvider';
import { Button } from '../src/ui/components';

jest.mock('@react-navigation/native', () => ({
  useFocusEffect: jest.fn(),
  useNavigation: jest.fn(),
}));
jest.mock('../src/storage/FavoritesProvider', () => ({ useFavorites: jest.fn() }));
jest.mock('../src/storage/LabProvider', () => ({ useLab: jest.fn() }));

const compound = { smiles: 'CCO', name: 'Ethanol', note: '' };
let tree;
let blur;
let navigation;
let lab;
let service;

function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

const analyzeButton = () => tree.root.findAllByType(Button).find(node =>
  ['Analisis ulang', 'Menganalisis…'].includes(node.props.label));

beforeEach(async () => {
  jest.clearAllMocks();
  navigation = { navigate: jest.fn() };
  lab = { save: jest.fn().mockResolvedValue(undefined) };
  service = { predict: jest.fn() };
  useNavigation.mockReturnValue(navigation);
  useLab.mockReturnValue(lab);
  useFavorites.mockReturnValue({ items: [compound], ready: true, error: null });
  useFocusEffect.mockImplementation(function useTestFocusEffect(effect) {
    React.useEffect(() => {
      const cleanup = effect();
      blur = cleanup;
      return cleanup;
    }, [effect]);
  });
  await act(async () => {
    tree = TestRenderer.create(<CollectionScreen service={service} />);
  });
});

afterEach(async () => {
  await act(async () => tree.unmount());
});

test('rapid reanalysis presses start one prediction and save one result', async () => {
  const pending = deferred();
  const result = { id: 'single-result' };
  service.predict.mockReturnValue(pending.promise);
  let request;
  await act(async () => {
    const press = analyzeButton().props.onPress;
    request = press();
    await press();
  });
  expect(service.predict).toHaveBeenCalledTimes(1);
  expect(analyzeButton().props.loading).toBe(true);

  await act(async () => {
    pending.resolve(result);
    await request;
  });
  expect(lab.save).toHaveBeenCalledTimes(1);
  expect(lab.save).toHaveBeenCalledWith(result);
  expect(navigation.navigate).toHaveBeenCalledTimes(1);
  expect(navigation.navigate).toHaveBeenCalledWith('Result', { result, saveError: null });
});

test('leaving Koleksi cancels the request and a late result cannot unlock a new analysis', async () => {
  const oldPending = deferred();
  const newPending = deferred();
  service.predict.mockReturnValueOnce(oldPending.promise).mockReturnValueOnce(newPending.promise);
  let oldRequest;
  await act(async () => { oldRequest = analyzeButton().props.onPress(); });
  const oldSignal = service.predict.mock.calls[0][0].signal;
  await act(async () => blur());
  expect(oldSignal.aborted).toBe(true);
  expect(analyzeButton().props.loading).toBe(false);

  let newRequest;
  await act(async () => { newRequest = analyzeButton().props.onPress(); });
  const newSignal = service.predict.mock.calls[1][0].signal;
  await act(async () => {
    oldPending.resolve({ id: 'cancelled-result' });
    await oldRequest;
  });
  expect(lab.save).not.toHaveBeenCalled();
  expect(navigation.navigate).not.toHaveBeenCalled();
  expect(analyzeButton().props.loading).toBe(true);
  expect(newSignal.aborted).toBe(false);
  await act(async () => analyzeButton().props.onPress());
  expect(service.predict).toHaveBeenCalledTimes(2);

  const result = { id: 'current-result' };
  await act(async () => {
    newPending.resolve(result);
    await newRequest;
  });
  expect(lab.save).toHaveBeenCalledTimes(1);
  expect(lab.save).toHaveBeenCalledWith(result);
  expect(navigation.navigate).toHaveBeenCalledWith('Result', { result, saveError: null });
});
