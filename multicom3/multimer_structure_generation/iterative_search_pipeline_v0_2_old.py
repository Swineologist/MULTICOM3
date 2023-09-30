import copy
import os
import sys
import time
from multicom3.common.util import makedir_if_not_exists, check_dirs
import pandas as pd
from multiprocessing import Pool
import dataclasses
from multicom3.tool.foldseek import *
import pickle
import numpy as np
from multicom3.monomer_templates_concatenation.sequence_based_pipeline import assess_hhsearch_hit
from multicom3.monomer_templates_concatenation.parsers import TemplateHit
from multicom3.multimer_structure_refinement.iterative_refine_pipeline_heteromer_v1_with_monomer import *
from multicom3.multimer_structure_refinement.util import *
from multicom3.monomer_alignment_generation.alignment import read_a3m
from multicom3.common.protein import complete_result

def search_templates_foldseek(foldseek_program, databases, inpdb, outdir):
    makedir_if_not_exists(outdir)
    foldseek_runner = Foldseek(binary_path=foldseek_program, databases=databases)
    return foldseek_runner.query(pdb=inpdb, outdir=outdir, progressive_threshold=2000)


class Multimer_iterative_generation_pipeline_monomer_old:

    def __init__(self, params, max_template_count=50):

        self.params = params

        self.max_iteration = 5

        self.max_template_count = max_template_count

    def concatenate_msa_and_templates(self,
                                      chain_id_map,
                                      template_results,
                                      alphafold_monomer_a3ms,
                                      outpath):

        prev_df = None
        for i, chain_id in enumerate(chain_id_map):
            templates = template_results[i]['all_alignment']
            curr_df = create_template_df(templates)
            curr_df = curr_df.add_suffix(f"{i + 1}")
            curr_df['tpdbcode'] = curr_df[f'tpdbcode{i + 1}']
            curr_df = curr_df.drop([f'tpdbcode{i + 1}'], axis=1)
            if prev_df is None:
                prev_df = curr_df
            else:
                prev_df = prev_df.merge(curr_df, how="inner", on='tpdbcode')

        keep_indices = []
        chain_template_multimer_msas = {}
        for chain_id in chain_id_map:
            chain_template_multimer_msas[chain_id] = {'desc': [chain_id],
                                                      'seq': [chain_id_map[chain_id].sequence]}

        print(prev_df)
        for i in range(len(prev_df)):
            template_infos = []
            for j, chain_id in enumerate(chain_id_map):
                template = prev_df.loc[i, f'template{j + 1}']
                qaln = prev_df.loc[i, f'aln_query{j + 1}']
                qstart = int(prev_df.loc[i, f'qstart{j + 1}'])
                qend = int(prev_df.loc[i, f'qend{j + 1}'])
                taln = prev_df.loc[i, f'aln_temp{j + 1}']
                tstart = prev_df.loc[i, f'tstart{j + 1}']
                tend = prev_df.loc[i, f'tend{j + 1}']
                evalue = float(prev_df.loc[i, f'evalue{j + 1}'])
                row_dict = dict(chainid=chain_id,
                                template=template,
                                tpdbcode=template[0:4],
                                aln_temp=taln,
                                tstart=tstart,
                                tend=tend,
                                aln_query=qaln,
                                qstart=qstart,
                                qend=qend,
                                evalue=evalue)
                template_infos += [row_dict]

            if not assess_complex_templates(chain_id_map, template_infos):
                continue

            keep_indices += [i]
            for j, chain_id in enumerate(chain_id_map):
                query_non_gaps = [res != '-' for res in prev_df.loc[i, f'aln_query{j + 1}']]
                out_sequence = ''.join(convert_taln_seq_to_a3m(query_non_gaps, prev_df.loc[i, f'aln_temp{j + 1}']))
                aln_full = ['-'] * len(chain_id_map[chain_id].sequence)

                qstart = int(prev_df.loc[i, f'qstart{j + 1}'])
                qend = int(prev_df.loc[i, f'qend{j + 1}'])
                aln_full[qstart - 1:qend] = out_sequence
                taln_full_seq = ''.join(aln_full)
                chain_template_multimer_msas[chain_id]['desc'] += [prev_df.loc[i, f'template{j + 1}']]
                chain_template_multimer_msas[chain_id]['seq'] += [taln_full_seq]

        msa_out_path = outpath
        makedir_if_not_exists(msa_out_path)

        out_multimer_msas = []
        out_monomer_msas = []
        for chain_idx, chain_id in enumerate(chain_id_map):
            fasta_chunks = (f">{chain_template_multimer_msas[chain_id]['desc'][i]}\n" \
                            f"{chain_template_multimer_msas[chain_id]['seq'][i]}"
                            for i in range(len(chain_template_multimer_msas[chain_id]['desc'])))
            chain_msa_temp_interact = os.path.join(msa_out_path, chain_id + '.temp.interact')
            with open(chain_msa_temp_interact, 'w') as fw:
                fw.write('\n'.join(fasta_chunks) + '\n')

            out_multimer_msa = os.path.join(msa_out_path, chain_id + '.iteration.multimer.a3m')
            os.system(f"cp {chain_msa_temp_interact} {out_multimer_msa}")

            out_multimer_msas += [out_multimer_msa]

            monomer_template_msas = {'desc': [], 'seq': []}
            seen_seqs = [chain_template_multimer_msas[chain_id]['seq'][i]
                         for i in range(len(chain_template_multimer_msas[chain_id]['desc']))]
            templates = template_results[chain_idx]['all_alignment']
            for i in range(len(templates)):
                query_non_gaps = [res != '-' for res in templates.loc[i, f'qaln']]
                out_sequence = ''.join(convert_taln_seq_to_a3m(query_non_gaps, templates.loc[i, f'taln']))
                aln_full = ['-'] * len(chain_id_map[chain_id].sequence)

                qstart = int(templates.loc[i, f'qstart'])
                qend = int(templates.loc[i, f'qend'])
                aln_full[qstart - 1:qend] = out_sequence
                taln_full_seq = ''.join(aln_full)

                if taln_full_seq not in seen_seqs:
                    monomer_template_msas['desc'] += [templates.loc[i, 'target']]
                    monomer_template_msas['seq'] += [taln_full_seq]

            fasta_chunks = (f">{monomer_template_msas['desc'][i]}\n{monomer_template_msas['seq'][i]}"
                            for i in range(len(monomer_template_msas['desc'])))
            
            msa_temp_monomer = os.path.join(msa_out_path, chain_id + '.temp.monomer')
            with open(msa_temp_monomer, 'w') as fw:
                fw.write('\n'.join(fasta_chunks) + '\n')

            iteration_monomer_a3m = os.path.join(msa_out_path, chain_id + ".iteration.monomer.a3m")
            combine_a3ms([alphafold_monomer_a3ms[chain_idx], msa_temp_monomer], iteration_monomer_a3m)
            out_monomer_msas += [iteration_monomer_a3m]

        interact_dict = {}
        msa_len = -1
        for i in range(0, len(out_multimer_msas)):
            msa_sequences, msa_descriptions = parse_fasta(out_multimer_msas[i])
            current_len = len(msa_descriptions)
            if msa_len == -1:
                msa_len = current_len
            elif current_len != msa_len:
                raise Exception(f"The length of each msas are not equal! {out_multimer_msas}")
            interact_dict[f'index_{i + 1}'] = [j for j in range(msa_len)]

        interact_df = pd.DataFrame(interact_dict)
        interact_csv = os.path.join(outpath, 'interaction.iteration.csv')
        interact_df.to_csv(interact_csv)

        top_template_files = []
        for template_result, chain_id in zip(template_results, chain_id_map):
            top_template_file = os.path.join(outpath, f"{chain_id}.top{self.max_template_count}")
            check_and_rank_monomer_templates_local_and_global(template_result=template_result,
                                                              outfile=top_template_file,
                                                              query_sequence=chain_id_map[chain_id].sequence,
                                                              max_template_count=self.max_template_count)
            top_template_files += [top_template_file]

        return top_template_files, out_multimer_msas, out_monomer_msas, interact_csv

    def copy_atoms_and_unzip(self, templates, outdir):
        os.chdir(outdir)
        for i in range(len(templates)):
            template_pdb = templates.loc[i, 'target']
            if template_pdb.find('.pdb.gz') > 0:
                template_path = os.path.join(self.params['foldseek_af_database_dir'], template_pdb)
                os.system(f"cp {template_path} {outdir}")
            else:
                template_path = os.path.join(self.params['foldseek_pdb_database_dir'], template_pdb)
                os.system(f"cp {template_path} {outdir}")
            os.system(f"gunzip -f {template_pdb}")

    def search_single(self, fasta_file, chain_id_map, monomer_pdb_dirs, monomer_alphafold_a3ms, outdir):

        fasta_file = os.path.abspath(fasta_file)

        targetname = pathlib.Path(fasta_file).stem

        print(f"Processing {targetname}")

        outdir = os.path.abspath(outdir)

        makedir_if_not_exists(outdir)

        cwd = os.getcwd()

        makedir_if_not_exists(outdir)

        out_model_dir = outdir

        prepare_dir = os.path.join(outdir, 'prepare')

        makedir_if_not_exists(prepare_dir)

        if not complete_result(out_model_dir, 5 * int(self.params['num_multimer_predictions_per_model'])):

            out_template_dir = os.path.join(outdir, 'templates')

            makedir_if_not_exists(out_template_dir)

            template_results = []
            alphafold_monomer_a3ms = []

            for chain_id in chain_id_map:

                monomer_work_dir = os.path.join(prepare_dir, chain_id)

                makedir_if_not_exists(monomer_work_dir)

                if not os.path.exists(monomer_alphafold_a3ms[chain_id]):
                    raise Exception(f"Cannot find the monomer final a3m in {monomer_alphafold_a3ms[chain_id]}")

                alphafold_monomer_a3m = os.path.join(outdir, chain_id + ".alphafold.monomer.a3m")
                os.system(f"cp {monomer_alphafold_a3ms[chain_id]} {alphafold_monomer_a3m}")

                alphafold_monomer_a3ms += [alphafold_monomer_a3m]

                chain_pdb = os.path.join(monomer_work_dir, chain_id + '.pdb')

                os.system(f"cp {monomer_pdb_dirs[chain_id]} {chain_pdb}")

                foldseek_res = search_templates_foldseek(
                    foldseek_program=self.params['foldseek_program'],
                    databases=[self.params['foldseek_pdb_database'], self.params['foldseek_af_database']],
                    inpdb=chain_pdb,
                    outdir=os.path.join(monomer_work_dir, 'foldseek'))

                if len(foldseek_res['all_alignment']) == 0:
                    print(
                        f"Cannot find any templates for {chain_id}")
                    break

                template_results += [foldseek_res]

                self.copy_atoms_and_unzip(templates=foldseek_res['all_alignment'],
                                          outdir=out_template_dir)

            if len(template_results) != len(chain_id_map):
                return None

            template_files, multimer_msa_files, monomer_msa_files, msa_pair_file = \
                self.concatenate_msa_and_templates(chain_id_map=chain_id_map,
                                                   template_results=template_results,
                                                   alphafold_monomer_a3ms=alphafold_monomer_a3ms,
                                                   outpath=outdir)

            if len(template_files) == 1:
                cmd = f"python {self.params['alphafold_multimer_program']} " \
                      f"--fasta_path {fasta_file} " \
                      f"--env_dir {self.params['alphafold_env_dir']} " \
                      f"--database_dir {self.params['alphafold_database_dir']} " \
                      f"--multimer_a3ms {','.join(multimer_msa_files)} " \
                      f"--monomer_a3ms {','.join(monomer_msa_files)} " \
                      f"--msa_pair_file {msa_pair_file} " \
                      f"--temp_struct_csv {template_files[0]} " \
                      f"--struct_atom_dir {out_template_dir} " \
                      f"--num_multimer_predictions_per_model {self.params['num_multimer_predictions_per_model']} " \
                      f"--multimer_num_ensemble {self.params['multimer_num_ensemble']} " \
                      f"--multimer_num_recycle {self.params['multimer_num_recycle']} " \
                      f"--output_dir {out_model_dir}"
            else:
                cmd = f"python {self.params['alphafold_multimer_program']} " \
                      f"--fasta_path {fasta_file} " \
                      f"--env_dir {self.params['alphafold_env_dir']} " \
                      f"--database_dir {self.params['alphafold_database_dir']} " \
                      f"--multimer_a3ms {','.join(multimer_msa_files)} " \
                      f"--monomer_a3ms {','.join(monomer_msa_files)} " \
                      f"--msa_pair_file {msa_pair_file} " \
                      f"--monomer_temp_csvs {','.join(template_files)} " \
                      f"--struct_atom_dir {out_template_dir} " \
                      f"--num_multimer_predictions_per_model {self.params['num_multimer_predictions_per_model']} " \
                      f"--multimer_num_ensemble {self.params['multimer_num_ensemble']} " \
                      f"--multimer_num_recycle {self.params['multimer_num_recycle']} " \
                      f"--output_dir {out_model_dir}"

            try:
                os.chdir(self.params['alphafold_program_dir'])
                print(cmd)
                os.system(cmd)
            except Exception as e:
                print(e)

        os.chdir(cwd)

    def concatenate_msa_and_templates_homo(self,
                                           chain_id_map,
                                           template_results,
                                           alphafold_monomer_a3ms,
                                           outpath):

        prev_df = None
        for i, chain_id in enumerate(chain_id_map):
            templates = template_results[i]['all_alignment']
            curr_df = create_template_df_with_index(templates)
            curr_df = curr_df.add_suffix(f"{i + 1}")
            curr_df['index'] = curr_df[f'index{i + 1}']
            curr_df = curr_df.drop([f'index{i + 1}'], axis=1)
            if prev_df is None:
                prev_df = curr_df
            else:
                prev_df = prev_df.merge(curr_df, how="inner", on='index')

        keep_indices = []
        chain_template_multimer_msas = {}
        for chain_id in chain_id_map:
            chain_template_multimer_msas[chain_id] = {'desc': [chain_id],
                                                      'seq': [chain_id_map[chain_id].sequence]}

        print(prev_df)
        for i in range(len(prev_df)):
            template_infos = []
            for j, chain_id in enumerate(chain_id_map):
                template = prev_df.loc[i, f'template{j + 1}']
                qaln = prev_df.loc[i, f'aln_query{j + 1}']
                qstart = int(prev_df.loc[i, f'qstart{j + 1}'])
                qend = int(prev_df.loc[i, f'qend{j + 1}'])
                taln = prev_df.loc[i, f'aln_temp{j + 1}']
                tstart = prev_df.loc[i, f'tstart{j + 1}']
                tend = prev_df.loc[i, f'tend{j + 1}']
                evalue = float(prev_df.loc[i, f'evalue{j + 1}'])
                row_dict = dict(chainid=chain_id,
                                template=template,
                                tpdbcode=template[0:4],
                                aln_temp=taln,
                                tstart=tstart,
                                tend=tend,
                                aln_query=qaln,
                                qstart=qstart,
                                qend=qend,
                                evalue=evalue)
                template_infos += [row_dict]

            # if not assess_complex_templates(chain_id_map, template_infos):
            #     continue

            keep_indices += [i]
            for j, chain_id in enumerate(chain_id_map):
                query_non_gaps = [res != '-' for res in prev_df.loc[i, f'aln_query{j + 1}']]
                out_sequence = ''.join(convert_taln_seq_to_a3m(query_non_gaps, prev_df.loc[i, f'aln_temp{j + 1}']))
                aln_full = ['-'] * len(chain_id_map[chain_id].sequence)

                qstart = int(prev_df.loc[i, f'qstart{j + 1}'])
                qend = int(prev_df.loc[i, f'qend{j + 1}'])
                aln_full[qstart - 1:qend] = out_sequence
                taln_full_seq = ''.join(aln_full)
                chain_template_multimer_msas[chain_id]['desc'] += [prev_df.loc[i, f'template{j + 1}']]
                chain_template_multimer_msas[chain_id]['seq'] += [taln_full_seq]

        msa_out_path = outpath
        makedir_if_not_exists(msa_out_path)

        out_monomer_msas = []
        for chain_idx, chain_id in enumerate(chain_id_map):
            fasta_chunks = (f">{chain_template_multimer_msas[chain_id]['desc'][i]}\n" \
                            f"{chain_template_multimer_msas[chain_id]['seq'][i]}"
                            for i in range(len(chain_template_multimer_msas[chain_id]['desc'])))
            
            msa_temp_interact = os.path.join(msa_out_path, chain_id + '.temp.interact')
            with open(msa_temp_interact, 'w') as fw:
                fw.write('\n'.join(fasta_chunks) + '\n')

            iteration_multimer_a3m = os.path.join(msa_out_path, chain_id + '.iteration.multimer.a3m')
            os.system(f"cp {msa_temp_interact} {iteration_multimer_a3m}")

            monomer_template_msas = {'desc': [], 'seq': []}
            seen_seqs = [chain_template_multimer_msas[chain_id]['seq'][i]
                         for i in range(len(chain_template_multimer_msas[chain_id]['desc']))]
            templates = template_results[chain_idx]['all_alignment']
            for i in range(len(templates)):
                query_non_gaps = [res != '-' for res in templates.loc[i, f'qaln']]
                out_sequence = ''.join(convert_taln_seq_to_a3m(query_non_gaps, templates.loc[i, f'taln']))
                aln_full = ['-'] * len(chain_id_map[chain_id].sequence)

                qstart = int(templates.loc[i, f'qstart'])
                qend = int(templates.loc[i, f'qend'])
                aln_full[qstart - 1:qend] = out_sequence
                taln_full_seq = ''.join(aln_full)

                if taln_full_seq not in seen_seqs:
                    monomer_template_msas['desc'] += [templates.loc[i, 'target']]
                    monomer_template_msas['seq'] += [taln_full_seq]

            fasta_chunks = (f">{monomer_template_msas['desc'][i]}\n{monomer_template_msas['seq'][i]}"
                            for i in range(len(monomer_template_msas['desc'])))
            msa_temp_monomer = os.path.join(msa_out_path, chain_id + '.temp.monomer')
            with open(msa_temp_monomer, 'w') as fw:
                fw.write('\n'.join(fasta_chunks) + '\n')

            iteration_monomer_a3m = os.path.join(msa_out_path, chain_id + '.iteration.monomer.a3m')
            combine_a3ms([iteration_multimer_a3m,
                          alphafold_monomer_a3ms[chain_idx],
                          msa_temp_monomer],
                        iteration_monomer_a3m)
            out_monomer_msas += [iteration_monomer_a3m]

        top_template_files = []
        for template_result, chain_id in zip(template_results, chain_id_map):
            top_template_file = os.path.join(outpath, f"{chain_id}.top{self.max_template_count}")
            check_and_rank_monomer_templates_local_and_global(template_result=template_result,
                                                              outfile=top_template_file,
                                                              query_sequence=chain_id_map[chain_id].sequence,
                                                              max_template_count=self.max_template_count)
            top_template_files += [top_template_file]

        return top_template_files, out_monomer_msas

    def search_single_homo(self, fasta_file, chain_id_map, monomer_pdb_dirs, monomer_alphafold_a3ms, outdir):

        fasta_file = os.path.abspath(fasta_file)

        targetname = pathlib.Path(fasta_file).stem

        print(f"Processing {targetname}")

        outdir = os.path.abspath(outdir)

        makedir_if_not_exists(outdir)

        cwd = os.getcwd()

        makedir_if_not_exists(outdir)

        out_model_dir = outdir

        prepare_dir = os.path.join(outdir, 'prepare')

        makedir_if_not_exists(prepare_dir)

        if not complete_result(out_model_dir, 5 * int(self.params['num_multimer_predictions_per_model'])):

            out_template_dir = os.path.join(prepare_dir, 'templates')

            makedir_if_not_exists(out_template_dir)

            template_results = []
            alphafold_monomer_a3ms = []

            for chain_id in chain_id_map:

                monomer_work_dir = os.path.join(prepare_dir, chain_id)

                makedir_if_not_exists(monomer_work_dir)

                if not os.path.exists(monomer_alphafold_a3ms[chain_id]):
                    raise Exception(f"Cannot find the monomer final a3m in {monomer_alphafold_a3ms[chain_id]}")

                monomer_alphafold_a3m = os.path.join(outdir, chain_id + ".alphafold.monomer.a3m")
                os.system(f"cp {monomer_alphafold_a3ms[chain_id]} {monomer_alphafold_a3m}")

                alphafold_monomer_a3ms += [monomer_alphafold_a3m]

                chain_pdb = os.path.join(monomer_work_dir, chain_id + '.pdb')

                os.system(f"cp {monomer_pdb_dirs[chain_id]} {chain_pdb}")

                foldseek_res = search_templates_foldseek(
                    foldseek_program=self.params['foldseek_program'],
                    databases=[self.params['foldseek_pdb_database'], self.params['foldseek_af_database']],
                    inpdb=chain_pdb,
                    outdir=os.path.join(monomer_work_dir, 'foldseek'))

                if len(foldseek_res['all_alignment']) == 0:
                    print(f"Cannot find any templates for {chain_id}")
                    break

                template_results += [foldseek_res]

                self.copy_atoms_and_unzip(templates=foldseek_res['all_alignment'],
                                          outdir=out_template_dir)

            if len(template_results) != len(chain_id_map):
                return None

            template_files, monomer_msa_files = \
                self.concatenate_msa_and_templates_homo(chain_id_map=chain_id_map,
                                                        template_results=template_results,
                                                        alphafold_monomer_a3ms=alphafold_monomer_a3ms,
                                                        outpath=outdir)

            if len(template_files) == 1:
                cmd = f"python {self.params['alphafold_multimer_program']} " \
                      f"--fasta_path {fasta_file} " \
                      f"--env_dir {self.params['alphafold_env_dir']} " \
                      f"--database_dir {self.params['alphafold_database_dir']} " \
                      f"--multimer_a3ms {','.join(monomer_msa_files)} " \
                      f"--monomer_a3ms {','.join(monomer_msa_files)} " \
                      f"--temp_struct_csv {template_files[0]} " \
                      f"--struct_atom_dir {out_template_dir} " \
                      f"--num_multimer_predictions_per_model {self.params['num_multimer_predictions_per_model']} " \
                      f"--multimer_num_ensemble {self.params['multimer_num_ensemble']} " \
                      f"--multimer_num_recycle {self.params['multimer_num_recycle']} " \
                      f"--output_dir {out_model_dir}"
            else:
                cmd = f"python {self.params['alphafold_multimer_program']} " \
                      f"--fasta_path {fasta_file} " \
                      f"--env_dir {self.params['alphafold_env_dir']} " \
                      f"--database_dir {self.params['alphafold_database_dir']} " \
                      f"--multimer_a3ms {','.join(monomer_msa_files)} " \
                      f"--monomer_a3ms {','.join(monomer_msa_files)} " \
                      f"--monomer_temp_csvs {','.join(template_files)} " \
                      f"--struct_atom_dir {out_template_dir} " \
                      f"--num_multimer_predictions_per_model {self.params['num_multimer_predictions_per_model']} " \
                      f"--multimer_num_ensemble {self.params['multimer_num_ensemble']} " \
                      f"--multimer_num_recycle {self.params['multimer_num_recycle']} " \
                      f"--output_dir {out_model_dir}"

            try:
                os.chdir(self.params['alphafold_program_dir'])
                print(cmd)
                os.system(cmd)
            except Exception as e:
                print(e)

        os.chdir(cwd)
