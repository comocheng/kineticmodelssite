# Voting Evidence: Complete Explanation

## What is Voting Evidence?

**Voting evidence** is the core mechanism by which `importChemkin.py` identifies unknown species in Chemkin mechanism files. It's a **reaction-based pattern matching system** that uses chemical reactions as "witnesses" to determine which RMG species matches each unknown Chemkin species.

---

## The Problem

When you have a Chemkin mechanism file like this:

```chemkin
SPECIES
CH4  CH3  C2H6  CO2(5)  H2O(3)  species_42  ...
END

REACTIONS
CH4 + OH = CH3 + H2O   1.0e13  0.0  8000
CH3 + CH3 = C2H6       3.6e13  0.0  0
species_42 + O2 = ???  2.1e12  0.0  12000
END
```

**Problem**: What is `species_42`? What is `CO2(5)`?

The species names in Chemkin files are arbitrary labels. You need to determine:
- What molecule each label represents (SMILES structure)
- Which RMG species database entry matches it

---

## The Solution: Reaction-Based Voting

### Step 1: Identify Easy Species First

Start by identifying species with unique formulas:

```
CH4  →  C       (methane - only one C1H4 molecule)
H2O  →  O       (water - only one H2O molecule)
O2   →  [O][O]  (oxygen - only one O2 molecule)
```

Also check thermo libraries for exact matches:
```
If thermo_chemkin(CO2) == thermo_library("carbon dioxide"):
    CO2 → O=C=O  ✓ Confirmed!
```

### Step 2: Generate RMG Reactions with Known Species

Add identified species to RMG's reactor core and generate reactions:

```python
# Add known species
rmg.reaction_model.add_species_to_core(CH4_species)
rmg.reaction_model.add_species_to_core(H2O_species)
rmg.reaction_model.add_species_to_core(OH_species)

# Generate reactions
rmg.reaction_model.enlarge()

# RMG produces:
# Reaction 1: CH4 + OH <=> CH3 + H2O  (H-abstraction)
# Reaction 2: CH3 + O2 <=> CH3O2      (addition)
# Reaction 3: CH3 + CH3 <=> C2H6      (recombination)
# ... hundreds more
```

### Step 3: Compare Reactions and Cast Votes

For each RMG reaction, check if it matches any Chemkin reaction:

```python
# RMG Reaction: CH4 + OH <=> CH3 + H2O
# Chemkin Reaction: CH4 + OH = CH3 + H2O

if reactions_match(rmg_rxn, chemkin_rxn):
    # All reactants/products align!
    # CH4 → CH4 ✓
    # OH → OH ✓
    # CH3 → ??? (unidentified)
    # H2O → H2O ✓
    
    # CAST VOTE:
    # "This reaction suggests CH3 in Chemkin is CH3 in RMG"
    votes['CH3'][<RMG CH3 species>].add((chemkin_rxn, rmg_rxn))
```

---

## Voting Evidence Structure

### Data Structure in importChemkin.py

```python
votes = {
    'CH3': {  # Chemkin label (unidentified)
        <RMG Species: CH3 radical>: [
            (chemkin_rxn1, rmg_rxn1),  # Reaction pair that voted
            (chemkin_rxn2, rmg_rxn2),
            (chemkin_rxn3, rmg_rxn3),
            # ... more voting reactions
        ],
        <RMG Species: CH3 cation>: [
            (chemkin_rxn10, rmg_rxn10),  # Different candidate!
        ]
    },
    'C2H5': {
        <RMG Species: ethyl radical>: [
            (chemkin_rxn4, rmg_rxn4),
            (chemkin_rxn5, rmg_rxn5),
        ]
    }
}
```

### Real Example from Test Data

Looking at the CO2 test data we created:

```python
CO2: {
    carbon dioxide(1) [O=C=O]: [
        ('Reaction_10_0_14', 'RMG_reaction_family_14'),
        ('Reaction_10_0_13', 'RMG_reaction_family_13'),
        ... 15 total votes
    ],
    carbon dioxide(2) [O=C=O]: [
        ('Reaction_10_1_9', 'RMG_reaction_family_9'),
        ('Reaction_10_1_8', 'RMG_reaction_family_8'),
        ... 10 total votes
    ],
    carbon dioxide(3) [O=C=OC]: [
        ('Reaction_10_2_14', 'RMG_reaction_family_14'),
        ('Reaction_10_2_13', 'RMG_reaction_family_13'),
        ... 15 total votes
    ]
}
```

---

## Unique vs Common Votes

### Unique Votes (High Value)

A **unique vote** is a reaction that votes for ONLY ONE candidate:

```
Reaction: CH3 + O2 = CH3OO

If this reaction ONLY matches:
  CH3 (radical) + O2 → CH3OO
  
But NOT:
  CH3 (cation) + O2 → ???
  CH3 (anion) + O2 → ???

Then this is a UNIQUE vote for CH3 (radical)!
```

**Why important?** Unique votes are discriminating evidence that helps distinguish between similar candidates.

### Common Votes (Lower Value)

A **common vote** is a reaction that votes for MULTIPLE candidates:

```
Reaction: CH3 + CH3 = C2H6

This matches:
  CH3 (radical) + CH3 (radical) → C2H6  ✓
  CH3 (cation) + CH3 (anion) → C2H6     ✓ (hypothetical)
  
COMMON vote - doesn't help distinguish!
```

**Why track them?** They still provide evidence that a species participates in certain reaction types.

---

## Vote Pruning Algorithm

After collecting all votes, `importChemkin.py` prunes common votes to focus on discriminating evidence:

```python
def prune_common_votes(votes):
    """
    Remove votes that don't help distinguish between candidates
    """
    for chemkin_label, candidates in votes.items():
        # Get all reactions for this species
        all_reactions = set()
        for candidate, reaction_pairs in candidates.items():
            for chemkin_rxn, rmg_rxn in reaction_pairs:
                all_reactions.add(chemkin_rxn)
        
        # For each reaction, check if it votes for multiple candidates
        for reaction in all_reactions:
            voting_for = []
            for candidate in candidates:
                if any(rxn == reaction for rxn, _ in candidates[candidate]):
                    voting_for.append(candidate)
            
            # If reaction votes for multiple candidates, mark as common
            if len(voting_for) > 1:
                for candidate in voting_for:
                    # Mark this vote as common (not unique)
                    mark_vote_as_common(chemkin_label, candidate, reaction)
```

---

## How Vote Evidence is Generated in importChemkin.py

### Main Loop

```python
def main(self):
    # 1. Load mechanism
    self.load_species()
    self.load_thermo()
    self.load_reactions()
    
    # 2. Auto-identify easy species
    self.identify_small_molecules()
    self.check_thermo_libraries()
    
    # 3. Main identification loop
    while not all_species_identified:
        
        # 4. Add identified species to RMG core
        for species in newly_identified:
            self.rmg_object.reaction_model.add_species_to_core(species)
        
        # 5. Generate new RMG reactions
        self.rmg_object.reaction_model.enlarge()
        new_reactions = self.rmg_object.reaction_model.edge.reactions
        
        # 6. Check reactions for matches
        self.check_reactions_for_matches(new_reactions)
        
        # 7. Analyze votes
        for chemkin_label, candidates in self.votes.items():
            # Prune common votes
            self.prune_common_votes(chemkin_label)
            
            # Calculate confidence scores
            for candidate in candidates:
                confidence = self.calculate_confidence(
                    chemkin_label, candidate
                )
            
            # Auto-confirm high-confidence matches
            if len(candidates) == 1 and confidence > 90:
                self.set_tentative_match(chemkin_label, candidate)
        
        # 8. Wait for user input on ambiguous cases
        if has_ambiguous_species:
            self.start_web_interface()
            wait_for_user_confirmation()
        
        # 9. Process user confirmations
        for confirmed_match in user_confirmations:
            self.set_match(chemkin_label, rmg_species)
            
            # Invalidate and re-check affected reactions
            invalidated = self.get_invalidated_reactions(
                chemkin_label, rmg_species
            )
            reactions_to_recheck.update(invalidated)
```

### check_reactions_for_matches() - The Voting Engine

```python
def check_reactions_for_matches(self, reactions_to_check):
    """
    Core voting algorithm
    """
    for edge_reaction in reactions_to_check:
        # Try to match with each Chemkin reaction
        for chemkin_reaction in self.chemkin_reactions_unmatched:
            
            # Check if reactions have same reactants/products
            match_found, suggested_matches = self.reactions_match(
                edge_reaction, 
                chemkin_reaction
            )
            
            if match_found:
                # Extract unidentified species mapping
                # e.g., {'CH3': <RMG CH3 species>}
                
                for chemkin_label, rmg_species in suggested_matches.items():
                    
                    # Validate: check formula matches
                    if not self.formula_matches(chemkin_label, rmg_species):
                        continue
                    
                    # Validate: check enthalpy is reasonable
                    delta_h = self.get_enthalpy_discrepancy(
                        chemkin_label, rmg_species
                    )
                    if abs(delta_h) > 200:  # >200 kJ/mol is suspicious
                        continue
                    
                    # CAST VOTE!
                    if chemkin_label not in self.votes:
                        self.votes[chemkin_label] = {}
                    
                    if rmg_species not in self.votes[chemkin_label]:
                        self.votes[chemkin_label][rmg_species] = set()
                    
                    # Store the reaction pair as evidence
                    self.votes[chemkin_label][rmg_species].add(
                        (chemkin_reaction, edge_reaction)
                    )
                    
                    # Remove from unmatched list
                    self.chemkin_reactions_unmatched.remove(chemkin_reaction)
                
                break  # Found match, move to next edge reaction
```

---

## Django Dashboard Implementation

### Vote Model in Django

```python
class Vote(models.Model):
    """
    A single vote: one reaction voting for one candidate
    """
    species = models.ForeignKey(Species, on_delete=models.CASCADE)
    candidate = models.ForeignKey(CandidateSpecies, on_delete=models.CASCADE)
    
    # The Chemkin reaction that cast this vote
    chemkin_reaction = models.CharField(max_length=500)
    
    # The matching RMG reaction
    rmg_reaction = models.CharField(max_length=500)
    rmg_reaction_family = models.CharField(max_length=100)
    
    # Is this a unique vote (only votes for this candidate)?
    is_unique = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['species', 'candidate', 'chemkin_reaction']
```

### Syncing from Cluster

```python
def sync_species_from_cluster(job):
    """
    Fetch voting data from cluster via SSH
    """
    # 1. SSH to cluster
    ssh = SSHClient()
    ssh.connect(job.cluster_address)
    
    # 2. Read progress.json file
    progress_data = load_json_from_cluster(
        ssh, 
        f"{job.remote_path}/progress.json"
    )
    
    # 3. Parse voting data
    for species_data in progress_data['unidentified_species']:
        chemkin_label = species_data['label']
        formula = species_data['formula']
        
        # Create or get Species
        species, created = Species.objects.get_or_create(
            job=job,
            chemkin_label=chemkin_label,
            defaults={'formula': formula}
        )
        
        # Create candidates
        for candidate_data in species_data['candidates']:
            candidate, created = CandidateSpecies.objects.get_or_create(
                species=species,
                rmg_label=candidate_data['rmg_label'],
                smiles=candidate_data['smiles'],
                defaults={
                    'enthalpy_discrepancy': candidate_data['delta_h'],
                    'vote_count': len(candidate_data['votes']),
                    'unique_vote_count': candidate_data['unique_votes']
                }
            )
            
            # Create votes
            for vote_data in candidate_data['votes']:
                Vote.objects.get_or_create(
                    species=species,
                    candidate=candidate,
                    chemkin_reaction=vote_data['chemkin_reaction'],
                    defaults={
                        'rmg_reaction': vote_data['rmg_reaction'],
                        'rmg_reaction_family': vote_data['family'],
                        'is_unique': vote_data['is_unique']
                    }
                )
```

---

## Visual Example: Complete Voting Workflow

### Scenario: Identifying CH3 (methyl radical)

```
Initial State:
  Known: CH4, OH, H2O, O2
  Unknown: CH3, C2H6, CH3OO

Step 1: Generate RMG Reactions
  RMG produces 100+ reactions including:
    R1: CH4 + OH → CH3 + H2O    (H-abstraction)
    R2: CH3 + O2 → CH3OO        (O2 addition)
    R3: CH3 + CH3 → C2H6        (recombination)

Step 2: Match with Chemkin Reactions
  Chemkin has:
    C1: CH4 + OH = CH3 + H2O    ← Matches R1!
    C2: CH3 + O2 = CH3OO        ← Matches R2!
    C3: CH3 + CH3 = C2H6        ← Matches R3!

Step 3: Cast Votes
  From C1 match:
    votes['CH3'][<RMG CH3 radical>].add((C1, R1))
  
  From C2 match:
    votes['CH3'][<RMG CH3 radical>].add((C2, R2))
    votes['CH3OO'][<RMG CH3OO>].add((C2, R2))
  
  From C3 match:
    votes['CH3'][<RMG CH3 radical>].add((C3, R3))
    votes['C2H6'][<RMG C2H6>].add((C3, R3))

Step 4: Analyze Votes
  CH3 candidates:
    - CH3 radical: 3 votes (all unique)
    - CH3 cation: 0 votes
    - CH3 anion: 0 votes
  
  Confidence: 100% (only candidate with votes)

Step 5: Auto-Confirm
  Set CH3 = CH3 radical (methyl)
  Save to SMILES.txt: CH3 [CH3]
```

---

## Summary

**What is voting evidence for?**
- **Identify unknown species** by analyzing reaction patterns
- **Distinguish between similar molecules** (e.g., CH3 radical vs cation)
- **Provide transparent evidence** for each identification
- **Enable user review** of ambiguous cases

**How is it generated?**
1. `importChemkin.py` generates RMG reactions with known species
2. Compares RMG reactions with Chemkin reactions
3. When reactions match, records votes for unidentified species
4. Prunes common votes to focus on discriminating evidence
5. Calculates confidence scores based on vote count, uniqueness, enthalpy
6. Presents to user via web interface (CherryPy → now Django!)

**Key Benefits:**
- ✅ **Evidence-based** - Every identification backed by chemical reactions
- ✅ **Transparent** - User can see exactly why a match was suggested
- ✅ **Automated** - High-confidence matches auto-confirmed
- ✅ **Interactive** - User confirms ambiguous cases
- ✅ **Validated** - Checks formula, enthalpy, thermo libraries

The voting evidence you see in the Django dashboard is pulled directly from this `importChemkin.py` process and displayed in a modern, user-friendly interface! 🎉
