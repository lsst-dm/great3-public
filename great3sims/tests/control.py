import great3sims
great3sims.constants.image_size_deg = .50
great3sims.constants.nrows = 10
great3sims.constants.ncols = 10
great3sims.constants.n_subfields = 1
great3sims.constants.xsize["ground"][True] = 64
great3sims.constants.ysize = great3sims.constants.xsize
great3sims.constants.n_subfields_per_field["constant"][True] = 1
great3sims.constants.subfield_grid_subsampling = 1
great3sims.constants.n_deep_subfields = 0
great3sims.constants.deep_frac = 0.0
great3sims.run(".", gal_dir="../../../COSMOS_23.5_training_sample", steps=["metaparameters", "catalogs", "config",], experiments=["control"], obs_type="ground", shear_type=["constant"], draw_psf_src = '../../../full_plane/lsst_e_80000003_f2.index', subfield_max=0)
