import great3sims
great3sims.run(".", gal_dir="tests/sample", truth_dir="truth", steps=["metaparameters", "catalogs", "config",], experiments=["real_galaxy"], obs_type="ground", shear_type=["constant"], draw_psf_src='tests/sample/real_galaxy_PSF_images_23.5_n20.fits')
