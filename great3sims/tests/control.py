from great3sims import constants, run
constants.image_size_deg = .50
constants.nrows = 10
constants.ncols = 10
constants.n_subfields = 1
constants.xsize["ground"][True] = 64
constants.ysize = constants.xsize
constants.n_subfields_per_field["constant"][True] = 1
constants.subfield_grid_subsampling = 1
constants.n_deep_subfields = 0
constants.deep_frac = 0.0
subfield_max = constants.n_subfields + constants.n_deep_subfields - 1
run("1", gal_dir="../../../COSMOS_23.5_training_sample", steps=["metaparameters", "catalogs", "config",], experiments=["control"], obs_type="ground", shear_type=["constant"], draw_psf_src = '1/control/ground/constant/psfs/psfs.index', subfield_max=subfield_max)
