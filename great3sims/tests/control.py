import great3sims
great3sims.run(".", gal_dir="tests/sample", steps=["metaparameters", "catalogs", "config",], experiments=["control"], obs_type="ground", shear_type=["constant"], draw_psf_src = 'tests/sample/real_galaxy_PSF_images_23.5_n20.fits')
