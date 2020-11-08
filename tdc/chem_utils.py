import pickle 
import numpy as np 
try: 
	import rdkit
	from rdkit import Chem, DataStructs
	from rdkit.Chem import AllChem
	from rdkit.Chem import Descriptors
	import rdkit.Chem.QED as QED
except:
	raise ImportError("Please install rdkit by 'conda install -c conda-forge rdkit'! ")	
try:
	from scipy.stats.mstats import gmean
except:
	raise ImportError("Please install rdkit by 'pip install scipy'! ") 
# import sascorer
try:
	from .score_modifier import *
	from .sascorer import * 
	from .drd2_scorer import get_score as drd2 
except:
	from score_modifier import *
	from sascorer import * 
	from drd2_scorer import get_score as drd2 


try:
	import networkx as nx 
except:
	raise ImportError("Please install networkx by 'pip install networkx'! ")	
## from https://github.com/wengong-jin/iclr19-graph2graph/blob/master/props/properties.py 
## from https://github.com/wengong-jin/multiobj-rationale/blob/master/properties.py 


def similarity(a, b):
	if a is None or b is None: 
		return 0.0
	amol = Chem.MolFromSmiles(a)
	bmol = Chem.MolFromSmiles(b)
	if amol is None or bmol is None:
		return 0.0
	fp1 = AllChem.GetMorganFingerprintAsBitVect(amol, 2, nBits=2048, useChirality=False)
	fp2 = AllChem.GetMorganFingerprintAsBitVect(bmol, 2, nBits=2048, useChirality=False)
	return DataStructs.TanimotoSimilarity(fp1, fp2) 



def qed(s):
	if s is None: 
		return 0.0
	mol = Chem.MolFromSmiles(s)
	if mol is None: 
		return 0.0
	return QED.qed(mol)

def penalized_logp(s):
	if s is None: 
		return -100.0
	mol = Chem.MolFromSmiles(s)
	if mol is None: 
		return -100.0

	logP_mean = 2.4570953396190123
	logP_std = 1.434324401111988
	SA_mean = -3.0525811293166134
	SA_std = 0.8335207024513095
	cycle_mean = -0.0485696876403053
	cycle_std = 0.2860212110245455

	log_p = Descriptors.MolLogP(mol)
	# SA = -sascorer.calculateScore(mol)
	SA = -calculateScore(mol)

	# cycle score
	cycle_list = nx.cycle_basis(nx.Graph(Chem.rdmolops.GetAdjacencyMatrix(mol)))
	if len(cycle_list) == 0:
		cycle_length = 0
	else:
		cycle_length = max([len(j) for j in cycle_list])
	if cycle_length <= 6:
		cycle_length = 0
	else:
		cycle_length = cycle_length - 6
	cycle_score = -cycle_length

	normalized_log_p = (log_p - logP_mean) / logP_std
	normalized_SA = (SA - SA_mean) / SA_std
	normalized_cycle = (cycle_score - cycle_mean) / cycle_std
	return normalized_log_p + normalized_SA + normalized_cycle


def SA(s):
	if s is None:
		return 100 
	mol = Chem.MolFromSmiles(s)
	if mol is None:
		return 100 
	SAscore = calculateScore(mol)
	return SAscore 	

'''
for gsk3 and jnk3, 
some code are borrowed from 
https://github.com/wengong-jin/multiobj-rationale/blob/master/properties.py 

'''
gsk3_model_path = 'oracle/gsk3.pkl'
with open(gsk3_model_path, 'rb') as f:
	gsk3_model = pickle.load(f)

def gsk3(smiles):
	molecule = smiles_to_rdkit_mol(smiles)
	fp = AllChem.GetMorganFingerprintAsBitVect(molecule, 2, nBits=2048)
	features = np.zeros((1,))
	DataStructs.ConvertToNumpyArray(fp, features)
	fp = features.reshape(1, -1) 
	gsk3_score = gsk3_model.predict_proba(fp)[0,1]
	return gsk3_score 

jnk3_model_path = 'oracle/jnk3.pkl'
with open(jnk3_model_path, 'rb') as f:
	jnk3_model = pickle.load(f)

def jnk3(smiles):
	molecule = smiles_to_rdkit_mol(smiles)
	fp = AllChem.GetMorganFingerprintAsBitVect(molecule, 2, nBits=2048)
	features = np.zeros((1,))
	DataStructs.ConvertToNumpyArray(fp, features)
	fp = features.reshape(1, -1) 
	jnk3_score = jnk3_model.predict_proba(fp)[0,1]
	return jnk3_score 	


def single_molecule_validity(smiles):
	if smiles.strip() == '':
		return False 
	mol = Chem.MolFromSmiles(smiles)
	if mol is None or mol.GetNumAtoms() == 0:
		return False 
	return True

def validity_ratio(list_of_smiles):
	valid_list_smiles = list(filter(single_molecule_validity, list_of_smiles))
	return 1.0*len(valid_list_smiles)/len(list_of_smiles)


def canonicalize(smiles):
	mol = Chem.MolFromSmiles(smiles)
	if mol is not None:
		return Chem.MolToSmiles(mol, isomericSmiles=True)
	else:
		return None

def unique_lst_of_smiles(list_of_smiles):
	canonical_smiles_lst = list(map(canonicalize, list_of_smiles))
	canonical_smiles_lst = list(filter(lambda x:x is not None, canonical_smiles_lst))
	canonical_smiles_lst = list(set(canonical_smiles_lst))
	return canonical_smiles_lst

def unique_rate(list_of_smiles):
	canonical_smiles_lst = unique_lst_of_smiles(list_of_smiles)
	return 1.0*len(canonical_smiles_lst)/len(list_of_smiles)

def novelty(new_smiles, smiles_database):
	new_smiles = unique_lst_of_smiles(new_smiles)
	smiles_database = unique_lst_of_smiles(smiles_database)
	novel_ratio = sum([1 if i in smiles_database else 0 for i in new_smiles])*1.0 / len(new_smiles)
	return novel_ratio

def diversity(list_of_smiles):
	"""
		The diversity of a set of molecules is defined as the average pairwise
		Tanimoto distance between the Morgan fingerprints ---- GCPN
	"""
	list_of_unique_smiles = unique_lst_of_smiles(list_of_smiles)
	list_of_mol = [Chem.MolFromSmiles(smiles) for smiles in list_of_unique_smiles]
	list_of_fp = [AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=2048, useChirality=False) for mol in list_of_mol]
	avg_lst = []
	for idx, fp in enumerate(list_of_fp):
		for fp2 in list_of_fp[idx+1:]:
			sim = DataStructs.TanimotoSimilarity(fp, fp2) 			
			avg_lst.append(sim)
	return np.mean(avg_lst)

def smiles_to_rdkit_mol(smiles):
	mol = Chem.MolFromSmiles(smiles)
	#  Sanitization check (detects invalid valence)
	if mol is not None:
		try:
			Chem.SanitizeMol(mol)
		except ValueError:
			return None
	return mol

def smiles_2_fingerprint_ECFP4(smiles):
	molecule = smiles_to_rdkit_mol(smiles)
	fp = AllChem.GetMorganFingerprint(molecule, 2)
	return fp 

def smiles_2_fingerprint_FCFP4(smiles):
	molecule = smiles_to_rdkit_mol(smiles)
	fp = AllChem.GetMorganFingerprint(molecule, 2, useFeatures=True)
	return fp 

def smiles_2_fingerprint_AP(smiles):
	molecule = smiles_to_rdkit_mol(smiles)
	fp = AllChem.GetAtomPairFingerprint(molecule, maxLength=10)
	return fp 

def smiles_2_fingerprint_ECFP6(smiles):
	molecule = smiles_to_rdkit_mol(smiles)
	fp = AllChem.GetMorganFingerprint(molecule, 3)
	return fp 

celecoxib_smiles = 'CC1=CC=C(C=C1)C1=CC(=NN1C1=CC=C(C=C1)S(N)(=O)=O)C(F)(F)F'
celecoxib_fp = smiles_2_fingerprint_ECFP4(celecoxib_smiles)
def celecoxib_rediscovery(test_smiles):
	# celecoxib_smiles = 'CC1=CC=C(C=C1)C1=CC(=NN1C1=CC=C(C=C1)S(N)(=O)=O)C(F)(F)F'
	# 'ECFP4'
	test_fp = smiles_2_fingerprint_ECFP4(test_smiles)
	similarity_value = DataStructs.TanimotoSimilarity(celecoxib_fp, test_fp)
	return similarity_value

Troglitazone_smiles='Cc1c(C)c2OC(C)(COc3ccc(CC4SC(=O)NC4=O)cc3)CCc2c(C)c1O'
Troglitazone_fp = smiles_2_fingerprint_ECFP4(Troglitazone_smiles)
def troglitazone_rediscovery(test_smiles):
	### ECFP4
	test_fp = smiles_2_fingerprint_ECFP4(test_smiles)
	similarity_value = DataStructs.TanimotoSimilarity(Troglitazone_fp, test_fp)
	return similarity_value	

Thiothixene_smiles='CN(C)S(=O)(=O)c1ccc2Sc3ccccc3C(=CCCN4CCN(C)CC4)c2c1'	
Thiothixene_fp = smiles_2_fingerprint_ECFP4(Thiothixene_smiles)
def thiothixene_rediscovery(test_smiles):
	### ECFP4
	test_fp = smiles_2_fingerprint_ECFP4(test_smiles)
	similarity_value = DataStructs.TanimotoSimilarity(Thiothixene_fp, test_fp)
	return similarity_value



Aripiprazole_smiles = 'Clc4cccc(N3CCN(CCCCOc2ccc1c(NC(=O)CC1)c2)CC3)c4Cl'
Aripiprazole_fp = smiles_2_fingerprint_FCFP4(Aripiprazole_smiles)
def aripiprazole_similarity(test_smiles):
	threshold = 0.75
	test_fp = smiles_2_fingerprint_FCFP4(test_smiles)
	similarity_value = DataStructs.TanimotoSimilarity(Aripiprazole_fp, test_fp)
	modifier = ClippedScoreModifier(upper_x=threshold)
	modified_similarity = modifier(similarity_value)
	return modified_similarity 

Albuterol_smiles = 'CC(C)(C)NCC(O)c1ccc(O)c(CO)c1'
Albuterol_fp = smiles_2_fingerprint_FCFP4(Albuterol_smiles)
def albuterol_similarity(test_smiles):
	threshold = 0.75
	test_fp = smiles_2_fingerprint_FCFP4(test_smiles)
	similarity_value = DataStructs.TanimotoSimilarity(Albuterol_fp, test_fp)
	modifier = ClippedScoreModifier(upper_x=threshold)
	modified_similarity = modifier(similarity_value)
	return modified_similarity 



Mestranol_smiles = 'COc1ccc2[C@H]3CC[C@@]4(C)[C@@H](CC[C@@]4(O)C#C)[C@@H]3CCc2c1'
Mestranol_fp = smiles_2_fingerprint_AP(Mestranol_smiles)
def mestranol_similarity(test_smiles):
	threshold = 0.75 
	test_fp = smiles_2_fingerprint_AP(test_smiles)
	similarity_value = DataStructs.TanimotoSimilarity(Mestranol_fp, test_fp)
	modifier = ClippedScoreModifier(upper_x=threshold)
	modified_similarity = modifier(similarity_value)
	return modified_similarity 

camphor_smiles = 'CC1(C)C2CCC1(C)C(=O)C2'
menthol_smiles = 'CC(C)C1CCC(C)CC1O'
camphor_fp = smiles_2_fingerprint_ECFP4(camphor_smiles)
menthol_fp = smiles_2_fingerprint_ECFP4(menthol_smiles)
def median1(test_smiles):
	# median mol between camphor and menthol, ECFP4 
	test_fp = smiles_2_fingerprint_ECFP4(test_smiles)
	similarity_v1 = DataStructs.TanimotoSimilarity(camphor_fp, test_fp)
	similarity_v2 = DataStructs.TanimotoSimilarity(menthol_fp, test_fp)
	similarity_gmean = gmean([similarity_v1, similarity_v2])
	return similarity_gmean


tadalafil_smiles = 'O=C1N(CC(N2C1CC3=C(C2C4=CC5=C(OCO5)C=C4)NC6=C3C=CC=C6)=O)C'
sildenafil_smiles = 'CCCC1=NN(C2=C1N=C(NC2=O)C3=C(C=CC(=C3)S(=O)(=O)N4CCN(CC4)C)OCC)C'
tadalafil_fp = smiles_2_fingerprint_ECFP6(tadalafil_smiles)
sildenafil_fp = smiles_2_fingerprint_ECFP6(sildenafil_smiles)
def median2(test_smiles):
	# median mol between tadalafil and sildenafil, ECFP6 
	test_fp = smiles_2_fingerprint_ECFP6(test_smiles)
	similarity_v1 = DataStructs.TanimotoSimilarity(tadalafil_fp, test_fp)
	similarity_v2 = DataStructs.TanimotoSimilarity(sildenafil_fp, test_fp)
	similarity_gmean = gmean([similarity_v1, similarity_v2])
	return similarity_gmean 


osimertinib_smiles = 'COc1cc(N(C)CCN(C)C)c(NC(=O)C=C)cc1Nc2nccc(n2)c3cn(C)c4ccccc34'
osimertinib_fp_fcfc4 = smiles_2_fingerprint_FCFP4(osimertinib_smiles)
osimertinib_fp_ecfc6 = smiles_2_fingerprint_ECFP6(osimertinib_smiles)

def osimertinib_mpo(test_smiles):

	sim_v1_modifier = ClippedScoreModifier(upper_x=0.8)
	sim_v2_modifier = MinGaussianModifier(mu=0.85, sigma=0.1)
	tpsa_modifier = MaxGaussianModifier(mu=100, sigma=10) 
	logp_modifier = MinGaussianModifier(mu=1, sigma=1) 

	molecule = smiles_to_rdkit_mol(test_smiles)
	fp_fcfc4 = smiles_2_fingerprint_FCFP4(test_smiles)
	fp_ecfc6 = smiles_2_fingerprint_ECFP6(test_smiles)
	tpsa_score = tpsa_modifier(Descriptors.TPSA(molecule))
	logp_score = logp_modifier(Descriptors.MolLogP(molecule))
	similarity_v1 = sim_v1_modifier(DataStructs.TanimotoSimilarity(osimertinib_fp_fcfc4, fp_fcfc4))
	similarity_v2 = sim_v2_modifier(DataStructs.TanimotoSimilarity(osimertinib_fp_ecfc6, fp_ecfc6))

	osimertinib_gmean = gmean([tpsa_score, logp_score, similarity_v1, similarity_v2])
	return osimertinib_gmean 

fexofenadine_smiles = 'CC(C)(C(=O)O)c1ccc(cc1)C(O)CCCN2CCC(CC2)C(O)(c3ccccc3)c4ccccc4'
fexofenadine_fp = smiles_2_fingerprint_AP(fexofenadine_smiles)
def Fexofenadine_mpo(test_smiles):
	similar_modifier = ClippedScoreModifier(upper_x=0.8)
	tpsa_modifier=MaxGaussianModifier(mu=90, sigma=10)
	logp_modifier=MinGaussianModifier(mu=4, sigma=1)

	molecule = smiles_to_rdkit_mol(test_smiles)
	fp_ap = smiles_2_fingerprint_AP(test_smiles)
	tpsa_score = tpsa_modifier(Descriptors.TPSA(molecule))
	logp_score = logp_modifier(Descriptors.MolLogP(molecule))
	similarity_value = similar_modifier(DataStructs.TanimotoSimilarity(fp_ap, fexofenadine_fp))
	fexofenadine_gmean = gmean([tpsa_score, logp_score, similarity_value])
	return fexofenadine_gmean 


# def Ranolazine_mpo(test_smiles):

# def Perindopril_mpo(test_smiles):



'''
    def get_AP(self, mol: Mol):
        return AllChem.GetAtomPairFingerprint(mol, maxLength=10)

    def get_PHCO(self, mol: Mol):
        return Generate.Gen2DFingerprint(mol, Gobbi_Pharm2D.factory)

    def get_BPF(self, mol: Mol):
        return GetBPFingerprint(mol)

    def get_BTF(self, mol: Mol):
        return GetBTFingerprint(mol)

    def get_PATH(self, mol: Mol):
        return AllChem.RDKFingerprint(mol)

    def get_ECFP4(self, mol: Mol):
        return AllChem.GetMorganFingerprint(mol, 2)

    def get_ECFP6(self, mol: Mol):
        return AllChem.GetMorganFingerprint(mol, 3)

    def get_FCFP4(self, mol: Mol):
        return AllChem.GetMorganFingerprint(mol, 2, useFeatures=True)

    def get_FCFP6(self, mol: Mol):
        return AllChem.GetMorganFingerprint(mol, 3, useFeatures=True)

'''




if __name__ == "__main__":
	smiles = '[H][C@@]12C[C@H](C)[C@](O)(C(=O)CO)[C@@]1(C)C[C@H](O)[C@@]1(F)[C@@]2([H])CCC2=CC(=O)C=C[C@]12C'
	smiles = 'CCC'
	smiles = '[NH3+][C@H](Cc1ccc(F)cc1)[C@H](O)C(=O)[O-]'
	smiles = 'c1ccc(-c2cnc(SC3CCCC3)n2Cc2ccco2)cc1'
	# print(similarity(smiles, smiles))
	# print(qed(smiles))
	# print(penalized_logp(smiles))
	# print(drd2(smiles))
	# print(SA(smiles))
	# list_of_smiles = ['CCC', 'fewjio', smiles, smiles]
	# print(validity_ratio(list_of_smiles))
	# print(unique_rate(list_of_smiles))
	# #  conda install -c rdkit rdkit
	# print(Mestranol_similarity(smiles))
	# print(median1(smiles))
	# print(median2(smiles))
	# print(osimertinib_mpo(smiles))
	# print(gsk3(smiles))
	# print(jnk3(smiles))
	print(Fexofenadine_mpo(smiles))




