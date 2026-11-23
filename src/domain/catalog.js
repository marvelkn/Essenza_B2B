import catalog from '../assets/catalog/compounds.json';
import additionalCompounds from '../assets/catalog/external-compounds.json';

const datasetStructures = new Set(catalog.compounds.map(item => item.smiles));

export const compounds = [...additionalCompounds, ...catalog.compounds];

export const isOutsideDataset = smiles => Boolean(smiles) && !datasetStructures.has(smiles);
