import great3sims
great3sims.run(".", gal_dir="../../../COSMOS_23.5_training_sample", truth_dir="truth", steps=["metaparameters", "catalogs", "config",], experiments=["real_galaxy"], obs_type="ground", shear_type=["constant"], draw_psf_src='sample_psfs/psfs.fits')
