import galsim
import pyfits
import os
import numpy as np
import math

from . import constants

def makeBuilder(real_galaxy, obs_type, shear_type, multiepoch, gal_dir, preload):
    """Return a GalaxyBuilder appropriate for the given options.

    @param[in] real_galaxy If True, we should use real galaxy images
                           instead of analytic models.
    @param[in] obs_type    Observation type: either "ground" or
                           "space"
    @param[in] shear_type  Shear type: either "constant" or "variable". 
                           (This information is used to decide on a scheme for shape
                           noise cancellation.)
    @param[in] multiepoch  If True, this is a multiepoch simulation, and this
                           is just the PSF of a single exposure.  If False,
                           the PSF should be that of a coadd with
                           constants.n_epochs epochs
    @param[in] gal_dir     Directory with galaxy catalog information.
    @param[in] preload     Preload the RealGalaxyCatalog for realistic galaxy branches?
    """
    return COSMOSGalaxyBuilder(real_galaxy=real_galaxy, obs_type=obs_type,
                               shear_type=shear_type, multiepoch=multiepoch,
                               gal_dir=gal_dir, preload=preload)

class GalaxyBuilder(object):

    def generateSubfieldParameters(self, rng, subfield_index):
        """Return a dict of metaparameters for the given subfield.
        These will be passed to generateCatalog when it is called.

        @param[in] rng             A galsim.UniformDeviate to be used for
                                   any random numbers.
        @param[in] subfield_index  Index of the simulated patch of sky.

        A "schema" entry is required in the returned dict: a list of
        (name, type) tuples that define the catalog fields that will
        be filled by this builder.  These field names may be used
        in catalogs that also have fields from other builders, so
        care should be taken to ensure each schema entry are unique.
        """
        raise NotImplementedError("GalaxyBuilder is abstract.")

    def generateCatalog(self, rng, catalog, parameters, variance, noise_mult, seeing):
        """Fill columns of the given catalog with per-object galaxy parameters.

        @param[in]     rng         A galsim.UniformDeviate to be used for any random numbers.
        @param[in,out] catalog     A structured NumPy array to fill.  The 'index', 'x',
                                   and 'y' columns will already be filled, and should be
                                   used when ensuring that the shape noise is pure B-mode.
                                   All columns defined by the 'schema' entry in the dict
                                   returned by generateSubfieldParameters() will also be present,
                                   and should be filled.  Other columns may be present as
                                   well, and should be ignored.
        @param[in]     parameters  A dict of metaparameters, as returned by the
                                   generateSubfieldParameters() method.
        @param[in]     variance    A typical noise variance that will be added, so we can avoid
                                   those galaxies with too high / low S/N.  This does not include
                                   any reduction in noise for the deep fields, so we can impose
                                   galaxy selection to get only those that would be seen in the
                                   non-deep fields at reasonable S/N.
        @param[in]     noise_mult  A factor by which the noise variance will be multiplied in actual
                                   image generation (will be <1 for deep fields).  This will be
                                   necessary so we can check that the requested noise variance is
                                   not below that in the real images, which would make image
                                   generation impossible for the real galaxy case.
        @param[in]     seeing      A value of seeing to use when applying cuts.  Can be None for
                                   space data (since in that case, the input seeing is ignored).
        """
        raise NotImplementedError("GalaxyBuilder is abstract.")

    def makeConfigDict(self):
        """Make the 'gal' portion of the config dict.
        """
        raise NotImplementedError("GalaxyBuilder is abstract.")

    def makeGalSimObject(self, record, parameters, xsize, ysize, rng):
        """Given a catalog record, a dict of metaparameters (as generated
        by generateCatalog() and generateSubfieldParameters(), respectively), and a
        galsim.UniformDeviate, return a pair of:
          - a galsim.GSObject that represents the galaxy (not including the shear
            due to lensing)
          - a galsim.CorrelatedNoise object that can be used to whiten the
            noise already present in the galaxy object, after the same shear
            and convolutions are applied to it as the galaxy object, or None
            if there is no noise in the galaxy object

        The returned galaxy should have all sizes in arcsec, though positional offsets can be
        specified in pixels when drawing in builder.py. Conversions can be performed using
        constants.pixel_scale when necessary.

        The maximum size of the postage stamp image that will be created is
        passed as well, to allow a RealGalaxy object to be noise-padded before
        the original pixel response is deconvolved from the noise (which should
        be done before it is returned).

        NOTE: if we want to use the galsim config interface to create images,
        we should replace this method with one that writes the relevant
        section of a config file.
        """
        raise NotImplementedError("GalaxyBuilder is abstract.")

def _gammafn(x):
    """The gamma function is present in python2.7's math module, but not 2.6.
    So try using that, and if it fails, use some code from RosettaCode:
    http://rosettacode.org/wiki/Gamma_function#Python
    """
    try:
        import math
        return math.gamma(x)
    except:
        y  = float(x) - 1.0;
        sm = _gammafn._a[-1];
        for an in _gammafn._a[-2::-1]:
            sm = sm * y + an;
        return 1.0 / sm;

_gammafn._a = ( 1.00000000000000000000, 0.57721566490153286061, -0.65587807152025388108,
              -0.04200263503409523553, 0.16653861138229148950, -0.04219773455554433675,
              -0.00962197152787697356, 0.00721894324666309954, -0.00116516759185906511,
              -0.00021524167411495097, 0.00012805028238811619, -0.00002013485478078824,
              -0.00000125049348214267, 0.00000113302723198170, -0.00000020563384169776,
               0.00000000611609510448, 0.00000000500200764447, -0.00000000118127457049,
               0.00000000010434267117, 0.00000000000778226344, -0.00000000000369680562,
               0.00000000000051003703, -0.00000000000002058326, -0.00000000000000534812,
               0.00000000000000122678, -0.00000000000000011813, 0.00000000000000000119,
               0.00000000000000000141, -0.00000000000000000023, 0.00000000000000000002
             )
 
class COSMOSGalaxyBuilder(GalaxyBuilder):
    """A GalaxyBuilder subclass for making COSMOS-based galaxies.
    """
    ## Decide on some meta-parameters.
    # What fraction of flux should we require there to be in the postage stamp?
    min_flux_frac = 0.99
    # What is minimum resolution factor to use?
    min_resolution = 1./3
    # Size rescaling to apply to simulate a fainter sample
    size_rescale = 0.6
    # Name for RealGalaxyCatalog files
    rgc_file = 'real_galaxy_catalog_23.5.fits'
    rgc_fits_file = 'real_galaxy_catalog_23.5_fits.fits'
    rgc_im_sel_file = 'real_galaxy_image_selection_info.fits'
    rgc_sel_file = 'real_galaxy_selection_info.fits'
    rgc_shapes_file = 'real_galaxy_23.5_shapes.fits'
    rgc_dmag_file = 'real_galaxy_deltamag_info.fits'
    rgc_mask_file = 'real_galaxy_mask_info.fits'
    # Minimum S/N to allow: something a bit below 20, so we don't have an absurdly sharp cutoff at
    # our target.
    sn_min = 17.0
    # Maximum S/N to allow: let's not try to make super bright objects that might not be used in a
    # typical shear analysis.
    sn_max = 100.0
    # Values of seeing for which we have precomputed results.
    min_ground_ind = 2 # array index 2 is the first for ground
    min_ground_fwhm = 0.5 # minimum value of FWHM for which results are tabulated
    ground_dfwhm = 0.15 # spacing between tabulated FWHM values
    ground_nfwhm = 4 # number of FWHM values for ground
    noise_fail_val = 1.e-10 # number to assign for negative noise variance values, then discard

    def __init__(self, real_galaxy, obs_type, shear_type, multiepoch, gal_dir, preload):
        """Construct for this type of branch.
        """
        # Basic parameters used by GalaxyBuilder to make decisions about galaxy population
        self.real_galaxy = real_galaxy
        self.obs_type = obs_type
        self.shear_type = shear_type
        self.multiepoch = multiepoch
        self.gal_dir = gal_dir
        if self.real_galaxy == True:
            self.preload = preload
        else:
            self.preload = False

    def generateSubfieldParameters(self, rng, subfield_index):
        # At this point, we only want to generate schema.  Everything else happens when making the
        # catalog.  The schema are different for real_galaxy and parametric galaxy branches.

        # We can only get here for the parametric galaxy case, so for now, just return schema for
        # that case.  Eventually we will have different ones based on the value of self.real_galaxy.
        # We'll also make a place-holder for approximate S/N value per galaxy based on pre-computed
        # numbers.  We will want to access this in our tests of the catalog.
        if self.real_galaxy:
            gal_schema = [("rot_angle_radians", float), ("gal_sn", float), ("cosmos_ident", int),
                          ("size_rescale", float), ("flux_rescale", float)]
        else:
            gal_schema=[("bulge_n", float), ("bulge_hlr", float),
                        ("bulge_q", float), ("bulge_beta_radians", float), ("bulge_flux", float),
                        ("disk_hlr", float), ("disk_q", float),
                        ("disk_beta_radians", float), ("disk_flux", float), ("gal_sn", float),
                        ("cosmos_ident", int), ("g1_intrinsic", float), ("g2_intrinsic", float)]
        return dict(schema=gal_schema)

    def generateCatalog(self, rng, catalog, parameters, variance, noise_mult, seeing=None):
        # Set up basic selection.
        # For space, the resolution and other selection criteria are one-dimensional arrays.
        # For ground, they are lists of galsim.LookupTables that can be used to interpolate to our
        # value of FWHM.  However, we should watch out for the min / max values of FWHM, so let's
        # check for those first.
        if self.obs_type == "ground":
            tmp_seeing = seeing
            if tmp_seeing < self.min_ground_fwhm:
                tmp_seeing = self.min_ground_fwhm
            max_ground_fwhm = self.min_ground_fwhm + self.ground_dfwhm*(self.ground_nfwhm-1)
            if tmp_seeing > max_ground_fwhm:
                tmp_seeing = max_ground_fwhm
        # For multi-epoch case, this is more complex since selection should take into account the
        # distribution of FWHM for all epochs.

        # If we haven't set up the catalog and such yet, do so now:
        if not hasattr(self,'rgc'):
            # Read in RealGalaxyCatalog, fits.
            # TODO: The question of preloading vs. not should be investigated once this branch
            # basically works.
            self.rgc = galsim.RealGalaxyCatalog(self.rgc_file, dir=self.gal_dir,
                                                preload=self.preload)
            self.fit_catalog = pyfits.getdata(os.path.join(self.gal_dir, self.rgc_fits_file))

            # Read in shapes file, to use for B-mode shape noise and for overall selection
            self.shapes_catalog = pyfits.getdata(os.path.join(self.gal_dir,
                                                              self.rgc_shapes_file))

            # Read in basic selection flags
            self.selection_catalog = pyfits.getdata(os.path.join(self.gal_dir, self.rgc_sel_file))
            # This vector is just a predetermined choice of whether to use bulgefit or sersicfit.
            self.use_bulgefit = self.selection_catalog.field('use_bulgefit')[:,0]

            # Read in selection flags based on the images:
            # Note: technically this isn't necessary for parametric fit branches, but in reality
            # these remove objects that we probably don't want in either place (e.g., too-low
            # surface brightness objects that show up as UFOs) and keep object selection consistent.
            self.im_selection_catalog = pyfits.getdata(os.path.join(self.gal_dir,
                                                                    self.rgc_im_sel_file))
            # Get the S/N in the original image, measured with an elliptical Gaussian filter
            # function.
            self.original_sn = self.im_selection_catalog.field('sn_ellip_gauss')
            # If it's a ground-based catalog, set up LookupTables to interpolate the minimum
            # variance post-whitening between FWHM values:
            if self.obs_type == "ground":
                fwhm_arr = self.min_ground_fwhm + self.ground_dfwhm*np.arange(self.ground_nfwhm)
                self.noise_min_var = []
                for obj in self.im_selection_catalog:
                    tmp_min_var = obj.field('min_var_white')[2:]
                    self.noise_min_var.append(galsim.LookupTable(fwhm_arr,tmp_min_var,f_log=True))
            # Otherwise, for space, save a single set of results depending on whether it's single
            # epoch (smaller pixels) or multiepoch (bigger pixels).
            else:
                if self.multiepoch:
                    self.noise_min_var = self.im_selection_catalog.field('min_var_white')[:,0]
                else:
                    self.noise_min_var = self.im_selection_catalog.field('min_var_white')[:,1]

            # Read in catalog that tells us how the galaxy magnitude from Claire's fits differs from
            # that in the COSMOS catalog.  This can be used to exclude total screwiness, objects
            # overly affected by blends, UFOs, and other junk like that.
            dmag_catalog = pyfits.getdata(os.path.join(self.gal_dir, self.rgc_dmag_file))
            self.dmag = dmag_catalog.field('delta_mag')

            # Read in the catalog that tells us which galaxies might have masking issues that make
            # the postage stamps too funky to use.
            mask_catalog = pyfits.getdata(os.path.join(self.gal_dir, self.rgc_mask_file))
            self.min_mask_dist_fraction = mask_catalog['min_mask_dist_fraction']
            self.min_mask_dist_pixels = mask_catalog['min_mask_dist_pixels']

            # If this is a ground-based calculation, then set up LookupTables to interpolate
            # max_variance and resolutions between FWHM values.
            if self.obs_type == "ground":
                self.noise_max_var = []
                self.flux_frac = []
                self.resolution = []
                for obj in self.selection_catalog:
                    tmp_max_var = obj.field('max_var')[1:]
                    if np.any(tmp_max_var < self.noise_fail_val):
                        tmp_max_var = np.zeros_like(tmp_max_var) + self.noise_fail_val
                    self.noise_max_var.append(galsim.LookupTable(fwhm_arr,tmp_max_var,f_log=True))
                    self.flux_frac.append(galsim.LookupTable(fwhm_arr,obj.field('flux_frac')[1:]))
                    self.resolution.append(galsim.LookupTable(fwhm_arr,obj.field('resolution')[1:]))
            # But if it's a space-based catalog, then just have arrays for each of the selection 
            # flags.
            else:
                self.noise_max_var = self.selection_catalog.field('max_var')[:,0]
                self.flux_frac = self.selection_catalog.field('flux_frac')[:,0]
                self.resolution = self.selection_catalog.field('resolution')[:,0]
 
        # First we set up the quantities that we need to apply basic selection, and that depend on
        # the type of simulation (ground / space, and ground-based seeing):
        #   able to measure shapes for basic tests of catalog
        #   fraction of flux in our postage stamp size [given seeing]
        #   resolution [given seeing]
        #   min noise variance post-whitening
        indices = np.arange(self.rgc.nobjects)
        if self.obs_type == "space":
            noise_max_var = self.noise_max_var
            flux_frac = self.flux_frac
            resolution = self.resolution
            noise_min_var = self.noise_min_var
        else:
            noise_max_var = np.zeros(self.rgc.nobjects)
            flux_frac = np.zeros(self.rgc.nobjects)
            resolution = np.zeros(self.rgc.nobjects)
            noise_min_var = np.zeros(self.rgc.nobjects)
            for gal_ind in range(self.rgc.nobjects):
                noise_max_var[gal_ind] = self.noise_max_var[gal_ind](tmp_seeing)
                flux_frac[gal_ind] = self.flux_frac[gal_ind](tmp_seeing)
                resolution[gal_ind] = self.resolution[gal_ind](tmp_seeing)
                noise_min_var[gal_ind] = self.noise_min_var[gal_ind](tmp_seeing)

        # We need to estimate approximate S/N values for each object, by comparing with a
        #   precalculated noise variance for S/N=20 that comes from using the fits.  Some of the
        #   values are junk for galaxies that have failure flags, so we will only do the calculation
        #   for those with useful values of noise_max_var.  Here we use the variance that isn't for
        #   deep fields even if we're in a deep field, because we want to require that the object
        #   would be seen at S/N>=20 if the field weren't deep.
        approx_sn_gal = np.zeros(self.rgc.nobjects)
        approx_sn_gal[noise_max_var > self.noise_fail_val] = \
            20.0*np.sqrt(noise_max_var[noise_max_var > self.noise_fail_val] / variance)

        # Apply all selections: (1) no problematic flags, (2) magnitudes in Claire's catalog and
        # COSMOS catalog should differ by <=1, (3) a large fraction of the flux should be
        # in the postage stamp, (4) object should be resolved, (5, 6) SN should be in the [min, max]
        # range, (7) maximum noise variance to add should not be nonsense.
        # And for variable shear, we need to require a shape to be used for B-mode shape noise.
        # This means proper flags, and |e| < 1.  However, for uniformity of selection we will also
        # impose this cut on constant shear sims.
        # In addition, for realistic galaxies, we require (a) that the S/N in the original image be
        # >=20 [really we want higher since we're adding noise, but mostly we're using this as a
        # loose filter to get rid of junk], and (b) that the requested noise variance in the sims
        # should be > the minimum noise variance that is possible post-whitening.  We impose these
        # even for parametric fits, just because the failures tend to be ones with problematic fits
        # as well.  Just for cut (b), we need to use the actual noise variance, which means
        # including a factor of decrease in the requested noise for deep subfields.  We don't
        # include any change in variance for multiepoch because the original noise gets decreased by
        # some factor as well.  We include a 10% fudge factor here because the minimum noise
        # variance post-whitening was estimated in a preprocessing step that didn't include some
        # details of the real simulations.
        # And yet another set of cuts: to avoid postage stamps with poor masking of nearby objects /
        # shredding of the central object, we apply two cuts on the minimum distance from the center
        # of the image to a masked pixel (absolute value, in pixels, and fractional distance in
        # terms of the postage stamp size).
        e1 = self.shapes_catalog.field('e1')
        e2 = self.shapes_catalog.field('e2')
        e_test = np.sqrt(e1**2 + e2**2)
        cond = np.logical_and.reduce(
            [self.selection_catalog.field('to_use') == 1,
             np.abs(self.dmag) < 0.8,
             flux_frac >= self.min_flux_frac,
             resolution >= self.min_resolution,
             approx_sn_gal >= self.sn_min,
             approx_sn_gal <= self.sn_max,
             noise_max_var > self.noise_fail_val,
             self.shapes_catalog.field('do_meas') > -0.5,
             e_test < 1.,
             self.original_sn >= 20.,
             noise_min_var <= 0.9*variance*noise_mult,
             self.min_mask_dist_fraction > 0.075,
             self.min_mask_dist_pixels > 8
             ])
        useful_indices = indices[cond]
        # Note on the two image-based cuts: without them, for some example run, we kept the following numbers
        # of galaxies -
        # ground (seeing 0.82): 11122
        # space: 34577
        # After imposing them, we kept the following numbers - 
        # ground: 10222 (cut 900, or 8%)
        # space: 33402 (cut 1175, or 4%)
        # Note that ~2400 objects out of 56k have S/N in the original image that is below our
        # threshold, but some of those must be eliminated by other cuts we're already making, which
        # is what I would have expected.  The S/N cut seems to be dominating over the minimum
        # variance cut by a lot, but I'm leaving the latter in for now in case it becomes more
        # important later if we change other things.
        # Note on the two mask cuts: when we impose these, the sample for space-based sims decreases
        # to 32966, another 4.5% decrease.

        # In the next bit, we choose a random selection of objects to use out of the above
        # candidates.  Note that this part depends on const vs. variable shear, since the number to
        # draw depends on the method of b-mode shape noise.
        if self.shear_type == "constant":
            n_to_select = constants.nrows*constants.ncols/2
        else:
            n_to_select = constants.nrows*constants.ncols

        # Select an index out of these, at random; however, need to apply size-dependent weight
        # because of failure to make postage stamps preferentially for large galaxies.
        #   Note: no weighting to account for known LSS fluctuations in COSMOS field.
        use_indices = np.zeros(n_to_select)
        for ind in range(n_to_select):
            # Select a random value in [0...len(useful_indices)-1], which tells the index in the
            # rgc.
            rand_value = int(np.floor(rng() * len(useful_indices)))
            rand_index = np.int(useful_indices[rand_value])

            # Also select a test random number from 0-1.
            test_rand = rng()

            # If that test random number is > the weight for that galaxy in the rgc, then try again;
            # otherwise, keep.
            while test_rand > self.rgc.weight[rand_index]:
                rand_value = int(np.floor(rng() * len(useful_indices)))
                rand_index = useful_indices[rand_value]
                test_rand = rng()
            use_indices[ind] = np.int(rand_index)

        # Set up arrays with indices and rotation angles to ensure shape noise cancellation.  The
        # method of doing this depends on the shear type.
        all_indices = np.zeros(constants.nrows*constants.ncols)
        rot_angle = np.zeros(constants.nrows*constants.ncols)
        # However, we first get some basic information about the galaxies which will be necessary
        # for tests of shape noise cancellation, whether for constant or variable shear.
        e1 = self.shapes_catalog.field('e1')
        e2 = self.shapes_catalog.field('e2')
        emag = np.sqrt(e1**2 + e2**2)
        ephi = 0.5 * np.arctan2(e2, e1)
        gmag = np.zeros_like(emag)
        if self.shear_type == "constant":
            # Make an array containing all indices (each repeated twice) but with rotation angle of
            # pi/2 for the second set.  Include a random rotation to get rid of any coherent shear
            # in the COSMOS galaxies.
            all_indices[0:n_to_select] = use_indices
            all_indices[n_to_select:constants.nrows*constants.ncols] = use_indices
            for ind in range(0,n_to_select):
                rot_angle[ind] = rng() * np.pi
            rot_angle[n_to_select:constants.nrows*constants.ncols] = np.pi/2. + \
                rot_angle[0:n_to_select]
            # But it would be kind of silly to include them in this order, so scramble them.  My
            # favorite python routine for this is np.random.permutation, but we have to make sure to
            # give it a random seed first (chosen from our own RNG) so that this process will be
            # repeatable.
            np.random.seed(int(rng() * 1000))
            perm_array = np.random.permutation(constants.nrows*constants.ncols)
            all_indices = all_indices[perm_array]
            rot_angle = rot_angle[perm_array]
        else:
            # First, generate a B-mode shape noise field.  We have to choose a variance based on the
            # p(|g|) for the galaxies that we're actually using.
            # Only do e->g conversion for those with |e|<1; those that violate that condition should
            # already have been excluded.
            gmag[emag<1.] = emag[emag<1.] / (1.0+np.sqrt(1.0 - emag[emag<1.]**2))
            g1 = gmag[use_indices.astype(int)] * np.cos(2.*ephi[use_indices.astype(int)])
            g2 = gmag[use_indices.astype(int)] * np.sin(2.*ephi[use_indices.astype(int)])
            gvar = g1.var() + g2.var()
            ps = galsim.PowerSpectrum(b_power_function=lambda k_arr : gvar*np.ones_like(k_arr))
            g1_b, g2_b = ps.buildGrid(grid_spacing=1., ngrid=constants.nrows, rng=rng)
            gmag_b = np.sqrt(g1_b**2 + g2_b**2)
            if np.any(gmag_b > 1.):
                # The shear field generated with this B-mode power function is not limited to
                # |g|<1.  We have to fix these:
                fix_ind = gmag_b > 1.
                g1_b[fix_ind] /= gmag_b[fix_ind]**2
                g2_b[fix_ind] /= gmag_b[fix_ind]**2
                gmag_b[fix_ind] = np.sqrt(g1_b[fix_ind]**2 + g2_b[fix_ind]**2)
            gphi_b = 0.5 * np.arctan2(g2_b, g1_b)

            # Match |g| between real galaxies and B-mode shape noise field according to ranking.
            ind_sorted_gmag_b = np.argsort(gmag_b.flatten())
            ind_sorted_gmag = np.argsort(gmag[use_indices.astype(int)].flatten())
            sorted_gmag_dict = {}
            for ind in range(constants.nrows * constants.ncols):
                sorted_gmag_dict[ind_sorted_gmag_b[ind]] = use_indices[ind_sorted_gmag[ind]]
            sorted_use_indices = np.array([sorted_gmag_dict[ind] 
                                           for ind in range(constants.nrows*constants.ncols)])
            target_beta = gphi_b.flatten()
            actual_beta = ephi[sorted_use_indices.astype(int)]
            all_indices = sorted_use_indices.astype(int)
            rot_angle = target_beta - actual_beta

        # To populate catalog with fluxes, we need the number of epochs into which the flux should
        # be split.
        if self.multiepoch:
            n_epochs = constants.n_epochs
        else:
            n_epochs = 1

        # Now that we know which galaxies to use in which order, and with what rotation angles, we
        # will populate the catalog.  The next bit of code depends quite a bit on whether it is a
        # real_galaxy or parametric galaxy experiment.  This is also where we specify flux and size
        # rescalings to mimic the deeper sample.
        ind = 0
        for record in catalog:
            record["cosmos_ident"] = self.fit_catalog[all_indices[ind]].field('ident')
            if self.real_galaxy:
                record["gal_sn"] = approx_sn_gal[all_indices[ind]]
                record["rot_angle_radians"] = rot_angle[ind]
                record["size_rescale"] = self.size_rescale
                record["flux_rescale"] = 1. / n_epochs
            else:
                # First save intrinsic shape information.
                if self.shear_type == "variable":
                    final_g = galsim.Shear(g = gmag[all_indices[ind]],
                                           beta=target_beta[ind]*galsim.radians)
                else:
                    final_g = galsim.Shear(
                        g = gmag[all_indices[ind]],
                        beta=(ephi[all_indices[ind]]+rot_angle[ind])*galsim.radians
                        )
                record["g1_intrinsic"] = final_g.g1
                record["g2_intrinsic"] = final_g.g2
                # Then save information that depends on whether we use 1- or 2-component fits.
                if self.use_bulgefit[all_indices[ind]] == 1.:
                    params = self.fit_catalog[all_indices[ind]].field('bulgefit')

                    bulge_q = params[11]
                    bulge_beta = params[15]*galsim.radians + rot_angle[ind]*galsim.radians
                    bulge_hlr = 0.03*self.size_rescale*np.sqrt(bulge_q)*params[9] # arcsec
                    # Factor of 0.03^2 in line below is because of Claire's normalization
                    # conventions when fitting.
                    # It is needed if we're drawing with 'flux' normalization convention.
                    bulge_flux = \
                        2.0*np.pi*3.607*(bulge_hlr**2)*params[8]/self.size_rescale**2/(0.03**2) 

                    disk_q = params[3]
                    disk_beta = params[7]*galsim.radians + rot_angle[ind]*galsim.radians
                    disk_hlr = 0.03*self.size_rescale*np.sqrt(disk_q)*params[1] # arcsec
                    disk_flux = \
                        2.0*np.pi*1.901*(disk_hlr**2)*params[0]/self.size_rescale**2/(0.03**2)

                    record["gal_sn"] = approx_sn_gal[all_indices[ind]]
                    bulge_frac = bulge_flux / (bulge_flux + disk_flux)
                    record["bulge_n"] = 4.0
                    record["bulge_hlr"] = bulge_hlr
                    record["bulge_q"] = bulge_q
                    record["bulge_beta_radians"] = bulge_beta/galsim.radians
                    record["bulge_flux"] = bulge_flux / n_epochs
                    record["disk_hlr"] = disk_hlr
                    record["disk_q"] = disk_q
                    record["disk_beta_radians"] = disk_beta/galsim.radians
                    record["disk_flux"] = disk_flux / n_epochs
                else:
                    # Make a single Sersic model instead
                    params = self.fit_catalog[all_indices[ind]].field('sersicfit')
                    gal_n = params[2]
                    # Fudge this if it is at the edge.  Now that GalSim #325 and #449 allow Sersic n
                    # in the range 0.3<=n<=6, the only problem is that Claire occasionally goes as
                    # low as n=0.2.
                    if gal_n < 0.3: gal_n = 0.3
                    gal_q = params[3]
                    gal_beta = params[7]*galsim.radians + rot_angle[ind]*galsim.radians
                    gal_hlr = 0.03*self.size_rescale*np.sqrt(gal_q)*params[1]
                    tmp_ser = galsim.Sersic(gal_n, half_light_radius=1.)
                    gal_bn = (1./tmp_ser.getScaleRadius())**(1./gal_n)
                    prefactor = gal_n * _gammafn(2.*gal_n) * math.exp(gal_bn) / (gal_bn**(2.*gal_n))
                    gal_flux = 2.*np.pi*prefactor*(gal_hlr**2)*params[0]/self.size_rescale**2/0.03**2
                    record["gal_sn"] = approx_sn_gal[all_indices[ind]]
                    record["bulge_n"] = gal_n
                    record["bulge_hlr"] = gal_hlr
                    record["bulge_q"] = gal_q
                    record["bulge_beta_radians"] = gal_beta/galsim.radians
                    record["bulge_flux"] = gal_flux / n_epochs
                    record["disk_hlr"] = 1.0
                    record["disk_q"] = 1.0
                    record["disk_beta_radians"] = 0.0
                    record["disk_flux"] = 0.0
            ind += 1

    def makeConfigDict(self):
        if self.real_galaxy:
            return self.makeConfigDictReal()
        else:
            return self.makeConfigDictParametric()

    def makeConfigDictParametric(self):
        d = {
            'type' : 'Sum',
            'items' : [
                {
                    'type' : 'Sersic',
                    'n' : { 'type' : 'Catalog', 'col' : 'bulge_n' },
                    'half_light_radius' : { 'type' : 'Catalog', 'col' : 'bulge_hlr' },
                    'ellip' : {
                        'type' : 'QBeta',
                        'q' : { 'type' : 'Catalog', 'col' : 'bulge_q' },
                        'beta' : { 'type' : 'Rad',
                                   'theta' : { 'type' : 'Catalog', 'col' : 'bulge_beta_radians' } 
                                 },
                    },
                    'flux' : { 'type' : 'Catalog', 'col' : 'bulge_flux' }
                },
                {
                    'type' : 'Exponential',
                    'half_light_radius' : { 'type' : 'Catalog', 'col' : 'disk_hlr' },
                    'ellip' : {
                        'type' : 'QBeta',
                        'q' : { 'type' : 'Catalog', 'col' : 'disk_q' },
                        'beta' : { 'type' : 'Rad',
                                   'theta' : { 'type' : 'Catalog', 'col' : 'disk_beta_radians' } 
                                 },
                    },
                    'flux' : { 'type' : 'Catalog', 'col' : 'disk_flux' }
                }
            ]
        }
        return d

    def makeConfigDictReal(self):
        noise_pad_size = int(np.ceil(constants.xsize[self.obs_type][self.multiepoch] *
                                     np.sqrt(2.) * 
                                     constants.pixel_scale[self.obs_type][self.multiepoch]))
        d = {
            'type' : 'RealGalaxy',
            'id' : { 'type' : 'Catalog', 'col' : 'cosmos_ident' },
            'noise_pad_size' : noise_pad_size,
            'dilate' : { 'type' : 'Catalog', 'col' : 'size_rescale' },
            'scale_flux' : { 'type' : 'Catalog', 'col' : 'flux_rescale' },
            'rotate' : { 'type' : 'Rad',
                         'theta' : { 'type' : 'Catalog', 'col' : 'rot_angle_radians' } 
                       },
            'whiten' : True
        }
        return d

    def makeGalSimObject(self, record, parameters, xsize, ysize, rng):
        if self.real_galaxy:
            return self.makeGalSimObjectReal(record, parameters, xsize, ysize, rng)
        else:
            return self.makeGalSimObjectParametric(record, parameters, xsize, ysize, rng)

    def makeGalSimObjectParametric(self, record, parameters, xsize, ysize, rng):
        # Specify sizes in arcsec.
        if record['bulge_flux'] > 0.:
            # First make a bulge
            bulge = galsim.Sersic(record['bulge_n'], flux = record['bulge_flux'],
                                  half_light_radius = record['bulge_hlr'])
            if record['bulge_q'] < 1.:
                bulge.applyShear(q=record['bulge_q'],
                                 beta=record['bulge_beta_radians']*galsim.radians)

        # Then optionally make a disk
        if record['disk_flux'] > 0.:
            disk = galsim.Exponential(flux = record['disk_flux'],
                                      half_light_radius = record['disk_hlr'])
            if record['disk_q'] < 1.:
                disk.applyShear(q=record['disk_q'],
                                beta=record['disk_beta_radians']*galsim.radians)
            if record['bulge_flux'] > 0.:
                return bulge+disk
            else:
                return disk
        else:
            return bulge

    def makeGalSimObjectReal(self, record, parameters, xsize, ysize, rng):
        # First set up the basic RealGalaxy.  But actually, to do that, we need to check that we
        # have a RealGalaxyCatalog already read in.  This happens in the generateCatalog step, but
        # if we are running great3.run() only for later steps in the analysis process, then
        # generateCatalog isn't run, so the galaxy builder won't have a stored RealGalaxyCatalog
        # attribute.  Check and read it in if necessary, before trying to make a RealGalaxy.
        if not hasattr(self,'rgc'):
            # Read in RealGalaxyCatalog, fits.
            # TODO: The question of preloading vs. not should be investigated once this branch
            # basically works.
            self.rgc = galsim.RealGalaxyCatalog(self.rgc_file, dir=self.gal_dir,
                                                preload=self.preload)
        noise_pad_size = int(np.ceil(constants.xsize[self.obs_type][self.multiepoch] *
                                     np.sqrt(2.) * 
                                     constants.pixel_scale[self.obs_type][self.multiepoch]))
        gal = galsim.RealGalaxy(self.rgc, rng=rng, id=record['cosmos_ident'],
                                noise_pad_size=noise_pad_size)
        
        # Rescale its size.
        gal.applyDilation(record['size_rescale'])
        # Rotate.
        gal.applyRotation(record['rot_angle_radians']*galsim.radians)
        # Rescale its flux.
        gal *= record['flux_rescale']
        # When we return the final noise object, we don't have to explicitly rescale its variance,
        # since the internal workings of this class take care of it for us.
        return gal
