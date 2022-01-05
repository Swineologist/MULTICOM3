import os, sys, argparse, time
from multiprocessing import Pool
from tqdm import tqdm
from bml_casp15.common.util import check_file, check_dir, check_dirs, makedir_if_not_exists, check_contents, \
    read_option_file
from bml_casp15.tool import hhblits
from bml_casp15.tool import jackhmmer
from bml_casp15.monomer_alignment_generation.pipeline import Monomer_alignment_generation_pipeline
from absl import flags
from absl import app

flags.DEFINE_string('option_file', None, 'option file')
flags.DEFINE_list('fasta_paths', None, 'Paths to FASTA files, paths should be separated by commas. '
                                       'All FASTA paths must have a unique basename as the basename is used to '
                                       'name the output directories for each prediction.')
flags.DEFINE_string('output_dir', None, 'Output directory')
FLAGS = flags.FLAGS


def generate_a3ms_for_single_seq(inparams):
    fasta, outdir, params = inparams

    uniref30 = params['uniref_db_dir'] + '/' + params['uniref_db']
    uniclust30 = params['uniclust_db_dir'] + '/' + params['uniclust_db']
    uniref90_fasta = params['uniref90_fasta']
    uniprot_fasta = params['uniprot_fasta']
    smallbfd = ""  # params['smallbfd_database']
    bfd = params['bfd_database']
    mgnify = params['mgnify_database']

    hhblits_binary = params['hhblits_program']
    jackhmmer_binary = params['jackhmmer_program']

    result = None
    try:
        pipeline = Monomer_alignment_generation_pipeline(jackhmmer_binary,
                                                         hhblits_binary,
                                                         uniref90_fasta,
                                                         mgnify,
                                                         smallbfd,
                                                         bfd,
                                                         uniref30,
                                                         uniclust30,
                                                         uniprot_fasta)
        result = pipeline.process(fasta, outdir)
    except Exception as e:
        return result
    return result


def main(argv):
    if len(argv) > 1:
        raise app.UsageError('Too many command-line arguments.')

    check_file(FLAGS.option_file)

    params = read_option_file(FLAGS.option_file)

    makedir_if_not_exists(FLAGS.output_dir)

    check_dirs(params, ['hhblits_program', 'jackhmmer_program'], isdir=False)

    process_list = []
    print("Start to generate alignments for monomers")
    monomer_list = FLAGS.fasta_paths
    for monomer in monomer_list:
        if not os.path.exists(monomer):
            print(f"Cannot find fasta file for {monomer}!")
            continue

        monomer_name = os.path.basename(monomer)
        outdir = FLAGS.output_dir + f"/{monomer_name[0:monomer_name.index('.fasta')]}"
        makedir_if_not_exists(outdir)

        os.system(f"cp {monomer} {outdir}")
        process_list.append([f"{outdir}/{monomer_name}", outdir, params])

    print(f"Total {len(process_list)} monomers to be processed")
    pool = Pool(processes=5)
    results = pool.map(generate_a3ms_for_single_seq, process_list)
    pool.close()
    pool.join()

    print("The alignment generation for monomers has finished!")


if __name__ == '__main__':
    flags.mark_flags_as_required([
        'option_file',
        'fasta_paths',
        'output_dir'
    ])
    app.run(main)
