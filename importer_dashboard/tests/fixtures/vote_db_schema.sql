-- The tables of an importer vote database (votes_<hash>.db), from importChemkin.py; schema only.
CREATE TABLE import_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT UNIQUE NOT NULL,
                model_name TEXT,
                species_file TEXT,
                reactions_file TEXT,
                thermo_file TEXT,
                status TEXT DEFAULT 'active',
                total_species INTEGER DEFAULT 0,
                identified_species INTEGER DEFAULT 0,
                total_reactions INTEGER DEFAULT 0,
                matched_reactions INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
CREATE TABLE species_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                chemkin_label TEXT NOT NULL,
                chemkin_formula TEXT,
                rmg_species_label TEXT,
                rmg_species_smiles TEXT,
                rmg_species_index INTEGER,
                rmg_species_formula TEXT,
                vote_count INTEGER DEFAULT 0,
                enthalpy_discrepancy REAL,
                confidence_score REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES import_jobs(job_id) ON DELETE CASCADE,
                UNIQUE(job_id, chemkin_label, rmg_species_index)
            );
CREATE TABLE voting_reactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                species_vote_id INTEGER NOT NULL,
                chemkin_reaction_str TEXT,
                edge_reaction_str TEXT,
                reaction_family TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (species_vote_id) REFERENCES species_votes(id) ON DELETE CASCADE
            );
CREATE TABLE identified_species (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                chemkin_label TEXT NOT NULL,
                chemkin_formula TEXT,
                rmg_species_label TEXT,
                rmg_species_smiles TEXT,
                rmg_species_index INTEGER,
                identification_method TEXT DEFAULT 'auto',
                identified_by TEXT,
                enthalpy_discrepancy REAL,
                notes TEXT,
                identified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES import_jobs(job_id) ON DELETE CASCADE,
                UNIQUE(job_id, chemkin_label)
            );
CREATE TABLE blocked_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                chemkin_label TEXT NOT NULL,
                rmg_species_label TEXT,
                rmg_species_smiles TEXT,
                rmg_species_index INTEGER,
                blocked_by TEXT,
                reason TEXT,
                blocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES import_jobs(job_id) ON DELETE CASCADE,
                UNIQUE(job_id, chemkin_label, rmg_species_index)
            );
CREATE TABLE thermo_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                species_vote_id INTEGER NOT NULL,
                library_name TEXT NOT NULL,
                library_species_name TEXT NOT NULL,
                name_matches BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (species_vote_id) REFERENCES species_votes(id) ON DELETE CASCADE,
                UNIQUE(species_vote_id, library_name, library_species_name)
            );
CREATE TABLE sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                sync_type TEXT NOT NULL,
                direction TEXT NOT NULL,
                record_count INTEGER,
                success BOOLEAN,
                error_message TEXT,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_id) REFERENCES import_jobs(job_id) ON DELETE CASCADE
            );
CREATE INDEX idx_species_votes_job_id 
            ON species_votes(job_id)
        ;
CREATE INDEX idx_species_votes_chemkin_label 
            ON species_votes(chemkin_label)
        ;
CREATE INDEX idx_identified_species_job_id 
            ON identified_species(job_id)
        ;
CREATE INDEX idx_blocked_matches_job_id 
            ON blocked_matches(job_id)
        ;
CREATE INDEX idx_thermo_matches_species_vote_id 
            ON thermo_matches(species_vote_id)
        ;
CREATE TABLE chemkin_reactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        reaction_index INTEGER NOT NULL,
        reaction_string TEXT NOT NULL,
        reactant_labels TEXT,
        product_labels TEXT,
        kinetics_type TEXT,
        kinetics_comment TEXT,
        is_matched BOOLEAN DEFAULT 0,
        is_identified BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES import_jobs(job_id) ON DELETE CASCADE,
        UNIQUE(job_id, reaction_index)
    );
CREATE INDEX idx_chemkin_reactions_job_id 
    ON chemkin_reactions(job_id)
;
CREATE INDEX idx_chemkin_reactions_matched 
    ON chemkin_reactions(job_id, is_matched)
;
