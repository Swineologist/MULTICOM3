# MULTICOM3
The system of improving AlphaFold2- and AlphaFold-Multimer-based predition of protein tertiary and quaternary structures by multiple sequene alignment sampling, template identification, model evaluation and model refinement.

## Overall workflow
![CASP15 pipeline](imgs/pipeline.png)

## Examples

![CASP15 pipeline](imgs/CASP15_good_examples1.png)
![CASP15 pipeline](imgs/CASP15_good_examples2.png)

# Installation


# Genetic databases

*   [BFD](https://bfd.mmseqs.com/),
*   [MGnify](https://www.ebi.ac.uk/metagenomics/),
*   [PDB70](http://wwwuser.gwdg.de/~compbiol/data/hhsuite/databases/hhsuite_dbs/),
*   [PDB](https://www.rcsb.org/) (structures in the mmCIF format),
*   [PDB seqres](https://www.rcsb.org/) – only for AlphaFold-Multimer,
*   [Uniclust30](https://uniclust.mmseqs.com/),
*   [UniProt](https://www.uniprot.org/uniprot/) – only for AlphaFold-Multimer,
*   [UniRef90](https://www.uniprot.org/help/uniref).

# Running the monomer/teritary structure prediction pipeline
```bash
python bin/monomer.py \
    --option_file bin/db_option \
    --fasta_path $YOUR_FASTA \
    --output_dir $OUTDIR
```
# Running the multimer/quaternary structure prediction pipeline
```bash
# For homo-multimer
# stoichiometry: A4
python bin/homomer.py \
    --option_file bin/db_option \
    --fasta_path $YOUR_FASTA \
    --stoichiometry $STOICHIOMETRY \ 
    --output_dir $OUTDIR

# For hetero-multimer
# stoichiometry: A1B1/A9B9C9
# stoichiometry2: heterodimer or heteromer
python bin/heteromer.py \
    --option_file bin/db_option \
    --fasta_path $YOUR_FASTA \
    --stoichiometry $STOICHIOMETRY \ 
    --stoichiometry2 $STOICHIOMETRY2 \ 
    --output_dir $OUTDIR
```

# Examples

## Folding a monomer

Say we have a monomer with the sequence `<SEQUENCE>`. The input fasta should be:

```fasta
>sequence_name
<SEQUENCE>
```

Then run the following command:

```bash
python bin/monomer.py \
    --option_file bin/db_option \
    --fasta_path monomer.fasta \
    --output_dir outdir
```

## Folding a homo-multimer

Say we have a homomer with 4 copies of the same sequence
`<SEQUENCE>`. The input fasta should be:

```fasta
>sequence_1
<SEQUENCE>
>sequence_2
<SEQUENCE>
>sequence_3
<SEQUENCE>
>sequence_4
<SEQUENCE>
```

Then run the following command:

```bash
python bin/homomer.py \
    --option_file bin/db_option \
    --fasta_path homomer.fasta \
    --stoichiometry A4 \ 
    --output_dir outdir
```

## Folding a hetero-multimer

Say we have an A2B3 heteromer, i.e. with 2 copies of
`<SEQUENCE A>` and 3 copies of `<SEQUENCE B>`. The input fasta should be:

```fasta
>sequence_1
<SEQUENCE A>
>sequence_2
<SEQUENCE A>
>sequence_3
<SEQUENCE B>
>sequence_4
<SEQUENCE B>
>sequence_5
<SEQUENCE B>
```

Then run the following command:

```bash
python bin/heteromer.py \
    --option_file bin/db_option \
    --fasta_path heteromer.fasta \
    --stoichiometry A2B3 \ 
    --stoichiometry2 heteromer \ 
    --output_dir outdir
```

## Output

# Citing this work

**If you use the code or data for monomer/tertiary structure prediction method in this package, please cite:**

Jumper, J., Evans, R., Pritzel, A., Green, T., Figurnov, M., Ronneberger, O., ... & Hassabis, D. (2021). Highly accurate protein structure prediction with AlphaFold. Nature, 596(7873), 583-589.
 
Liu, J., Guo, Z., Wu, T., Roy, R. S., Chen, C., & Cheng, J. (2023). Improving AlphaFold2-based Protein Tertiary Structure Prediction with MULTICOM in CASP15. bioRxiv, 2023-05.

**In addition, if you use the multimer/quaternary structure prediction method, please cite:**

Evans, R., O’Neill, M., Pritzel, A., Antropova, N., Senior, A., Green, T., ... & Hassabis, D. (2021). Protein complex prediction with AlphaFold-Multimer. BioRxiv, 2021-10.
