# Role-Specific Knowledge Base Data

Place role-specific knowledge base documents (PDFs, rubrics, domain guides, and job specifications) in this directory or categorized subdirectories.

### Recommended Structure:
```
data/
├── software_engineer/
│   ├── system_design_rubric.pdf
│   └── backend_competencies.pdf
├── data_scientist/
│   ├── ml_evaluation_criteria.pdf
│   └── stats_domain_guide.pdf
└── product_manager/
    └── product_execution_rubric.pdf
```

The ingestion service will process PDFs placed here, chunk them, and store embeddings into ChromaDB with metadata referencing the `target_role`.
