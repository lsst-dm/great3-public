#!/usr/bin/env python

# Copyright (c) 2014, the GREAT3 executive committee (http://www.great3challenge.info/?q=contacts)
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are permitted
# provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this list of conditions
# and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright notice, this list of
# conditions and the following disclaimer in the documentation and/or other materials provided with
# the distribution.
#
# 3. Neither the name of the copyright holder nor the names of its contributors may be used to
# endorse or promote products derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR
# IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER
# IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT
# OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""Has been used to perform various tests on the variable shear branch catalogs, mostly consistency
with expectations and the presence of B-mode leakage.

Currently compares the map_E output of server/great3/evaluate.py versus that which comes from
running presubmisson.py (assumed to be stored in ../../great3-public/presubmission_script/),
plotting the results.  However, module has tools which can be used for a number of related 
investigations.
"""

import os
import sys
import numpy as np
import constants
sys.path.append("..")
sys.path.append(os.path.join("..", "server", "great3"))
import great3sims.mapper
import evaluate
import test_evaluate

TEST_DIR = os.path.join("..", "tests", "test_run")  # Location where the intrinsic shear catalogues
                                                    # are stored (after being built by test_run.py)

def get_field(subfield_index, nsubfields_per_field=evaluate.NSUBFIELDS_PER_FIELD):
    return subfield_index / nsubfields_per_field

def get_subfield_within_field(subfield_index, nsubfields_per_field=evaluate.NSUBFIELDS_PER_FIELD):
    return subfield_index % nsubfields_per_field

def make_fits_cats(idarray, g1array, g2array, dir="./cats", prefix="vartest", silent=True):
    """Make a whole series of FITS catalogues of the sort expected by Melanie's presubmission.py
    script.
    
    Writes a whole series of catalogues named <prefix>-000.fits, <prefix>-001.fits etc. to the
    folder specified as `dir`.
    """
    import pyfits
    if g1array.shape != g2array.shape:
        raise ValueError("Input g1true and g2true must be same shape")
    if g1array.shape != (
        evaluate.NGALS_PER_SUBFIELD, evaluate.NSUBFIELDS_PER_FIELD, evaluate.NFIELDS):
        raise ValueError(
            "Input truth shear arrays do not match shape expected for GREAT3 simulations")
    # Loop over subfields making the catalogues
    for subfield_index in range(evaluate.NSUBFIELDS):

       field_index = get_field(subfield_index)
       subfield_within_field_index = get_subfield_within_field(subfield_index)
       g1 = g1array[:, subfield_within_field_index, field_index]
       g2 = g2array[:, subfield_within_field_index, field_index]
       identifier = idarray[:, subfield_within_field_index, field_index]
       col0 = pyfits.Column(name='ID', format='9A', array=identifier)    
       col1 = pyfits.Column(name='g1', format='E', array=g1)
       col2 = pyfits.Column(name='g2', format='E', array=g2)
       col3 = pyfits.Column(name='w', format='E', array=np.ones_like(g1))
       cols = pyfits.ColDefs([col0, col1, col2, col3])
       tbhdu = pyfits.new_table(cols)
       prhdu = pyfits.PrimaryHDU()
       thdulist = pyfits.HDUList([prhdu, tbhdu])
       outfile = os.path.join(dir, prefix+("-%03d" % subfield_index)+".fits")
       if not silent:
           print "Saving FITS catalogue to "+outfile
           thdulist.writeto(outfile, clobber=True)
       else:
           if os.path.isfile(outfile): os.remove(outfile)
           thdulist.writeto(outfile)
    return

def get_variable_gsuffix(experiment, obs_type, suffix="_intrinsic", file_prefix="galaxy_catalog",
                         logger=None, test_dir=TEST_DIR):
    """Get the full catalog of intrinsic "shears" and positions for all fields.

    Gets "g1"+suffix and "g2"+suffix from the subfield_catalog files.

    @return id, x, y, g1, g2
    """
    mapper = great3sims.mapper.Mapper(test_dir, experiment, obs_type, "variable")
    identifier = np.empty(
        (evaluate.NGALS_PER_SUBFIELD, evaluate.NSUBFIELDS_PER_FIELD, evaluate.NFIELDS), dtype=int)
    g1int = np.empty(
        (evaluate.NGALS_PER_SUBFIELD, evaluate.NSUBFIELDS_PER_FIELD, evaluate.NFIELDS))
    g2int = np.empty(
        (evaluate.NGALS_PER_SUBFIELD, evaluate.NSUBFIELDS_PER_FIELD, evaluate.NFIELDS))
    xx = np.empty(
        (evaluate.NGALS_PER_SUBFIELD, evaluate.NSUBFIELDS_PER_FIELD, evaluate.NFIELDS))
    yy = np.empty(
        (evaluate.NGALS_PER_SUBFIELD, evaluate.NSUBFIELDS_PER_FIELD, evaluate.NFIELDS))
    # Load the offsets
    subfield_indices, offset_deg_x, offset_deg_y = evaluate.get_generate_variable_offsets(
        experiment, obs_type, storage_dir=evaluate.STORAGE_DIR, truth_dir=evaluate.TRUTH_DIR,
        logger=logger)
    # Build basic x and y grids to use for coord positions
    xgrid_deg, ygrid_deg = np.meshgrid(
        np.arange(0., evaluate.XMAX_GRID_DEG, evaluate.DX_GRID_DEG),
        np.arange(0., evaluate.XMAX_GRID_DEG, evaluate.DX_GRID_DEG))
    xgrid_deg = xgrid_deg.flatten() # Flatten these - the default C ordering corresponds to the way
    ygrid_deg = ygrid_deg.flatten() # the shears are ordered too, which is handy
    if len(xgrid_deg) != evaluate.NGALS_PER_SUBFIELD:
        raise ValueError(
            "Dimensions of xgrid_deg and ygrid_deg do not match NGALS_PER_SUBFIELD.  Please check "+
            "the values of XMAX_GRID_DEG and DX_GRID_DEG in evaluate.py.")
    # Then loop over the fields and subfields getting the galaxy catalogues
    import pyfits
    for ifield in range(evaluate.NFIELDS):

        # Read in all the shears in this field and store
        for jsub in range(evaluate.NSUBFIELDS_PER_FIELD):

            # Build the x,y grid using the subfield offsets
            isubfield_index = jsub + ifield * evaluate.NSUBFIELDS_PER_FIELD
            xx[:, jsub, ifield] = xgrid_deg + offset_deg_x[isubfield_index]
            yy[:, jsub, ifield] = ygrid_deg + offset_deg_y[isubfield_index]
            galcatfile = os.path.join(
                mapper.full_dir, (file_prefix+"-%03d.fits" % isubfield_index))
            truedata = pyfits.getdata(galcatfile)
            if len(truedata) != evaluate.NGALS_PER_SUBFIELD:
                raise ValueError(
                    "Number of records in "+galcatfile+" (="+str(len(truedata))+") is not "+
                    "equal to NGALS_PER_SUBFIELD (="+str(evaluate.NGALS_PER_SUBFIELD)+")")
            g1int[:, jsub, ifield] = truedata["g1"+suffix]
            g2int[:, jsub, ifield] = truedata["g2"+suffix]
            identifier[:, jsub, ifield] = truedata["ID"]

    # Then return
    return identifier, xx, yy, g1int, g2int

def add_submissions(sub1file, sub2file, outfile):
    """Add two submissions.  Errors added in quadrature.
    """
    print "Adding "+sub2file+" to "+sub1file
    sub1 = np.loadtxt(sub1file)
    sub2 = np.loadtxt(sub2file)
    field = sub1[:, 0]
    theta = sub1[:, 1]
    mapE = sub1[:, 2] + sub2[:, 2]
    mapB = sub1[:, 3] + sub2[:, 3]
    maperr = np.sqrt(sub1[:, 4]**2 + sub2[:, 4]**2)
    np.savetxt(outfile, np.array((field, theta, mapE, mapB, maperr)).T, fmt="%d %f %e %e %e")
    return

def subtract_submissions(sub1file, sub2file, outfile):
    """Subtract submission 2 from submission 1 and save to outfile.  Errors added in quadrature.
    """
    print "Subtracting "+sub2file+" from "+sub1file
    sub1 = np.loadtxt(sub1file)
    sub2 = np.loadtxt(sub2file)
    field = sub1[:, 0]
    theta = sub1[:, 1]
    mapE = sub1[:, 2] - sub2[:, 2]
    mapB = sub1[:, 3] - sub2[:, 3]
    maperr = np.sqrt(sub1[:, 4]**2 + sub2[:, 4]**2)
    np.savetxt(outfile, np.array((field, theta, mapE, mapB, maperr)).T, fmt="%d %f %e %e %e")
    return

def run_variable_tests():
    """Run some variable shear tests (tests that were happening around ~30 Sep - 6 Oct 2013, so
    removed from the main module text and retired here)"
    """
    # Make intermediate catalogues for control space variable
    idt, xt, yt, g1t, g2t = get_variable_gsuffix("control", "space", suffix="") # True = g1/g2 only
    idi, xi, yi, g1i, g2i = get_variable_gsuffix("control", "space", suffix="_intrinsic")
    ret = make_fits_cats(idt, g1t, g2t, prefix="gtrue")
    ret = make_fits_cats(idi, g1i, g2i, prefix="gintrinsic")
    # Make a test set with gtrue plus gintrinsic, will be used for a later test
    gintc = g1i + g2i*1j   # Use complex notation, see e.g. Schneider 2006, eq 12
    gtruec = g1t + g2t*1j  #
    gfinalc = (gintc + gtruec) / (1. + gtruec.conj() * gintc)
    ret = make_fits_cats(idi, gfinalc.real, gfinalc.imag, prefix="gtrue_intrinsic")
    # Now we run the presubmission script via presubmisions-alpha-2 (hacked to not do ID checks)
    import subprocess
    import glob
    gtruesubfile = "./submissions/gtrue_csv.asc"
    call_list = [
        "./presubmission_alpha-2", "-b", "control-space-variable",
        "-o", gtruesubfile, ]+glob.glob("./cats/gtrue-*")
    subprocess.check_call(call_list)
    gintsubfile = "./submissions/gintrinsic_kmin1kmax12_csv.asc"
    call_list = [
        "./presubmission_alpha-2", "-b", "control-space-variable",
        "-o", gintsubfile, ]+glob.glob("./cats/gintrinsic-*")
    subprocess.check_call(call_list)
    gtrueintsubfile = "./submissions/gtrue_intrinsic_kmin1kmax12_csv.asc"
    call_list = [
        "./presubmission_alpha-2", "-b", "control-space-variable",
        "-o", gtrueintsubfile, ]+glob.glob("./cats/gtrue_intrinsic-*")
    subprocess.check_call(call_list)

    # Create a "corrected" submission by subtracting off the difference
    subtract_submissions(
        gtrueintsubfile, gintsubfile, "./submissions/gcorrected_kmin1kmax12_csv.asc")

    # Plot
    import plot_variable_submission
    plot_variable_submission.plot(gtruesubfile, gtruesubfile.rstrip(".asc")+".png")
    plot_variable_submission.plot(gintsubfile, gintsubfile.rstrip(".asc")+".png")
    plot_variable_submission.plot(gtrueintsubfile, gtrueintsubfile.rstrip(".asc")+".png")
    plot_variable_submission.plot(
        "./submissions/gcorrected_kmin1kmax12_csv.asc",
        "./submissions/gcorrected_kmin1kmax12_csv.png")
    # Move all the pngs to plots/
    subprocess.check_call(["mv",]+glob.glob("./submissions/*.png")+["./plots/"])


if __name__ == "__main__":

    #run_variable_tests()
    import glob
    import subprocess
    import logging

    # Setup the logger
    logging.basicConfig(stream=sys.stderr)
    logger = logging.getLogger("test")
    logger.setLevel(logging.DEBUG)

    # First get the mapEtruth version
    fieldt, thetat, map_Et, map_Bt, maperrt = evaluate.get_generate_variable_truth(
        "control", "space", truth_dir="/Users/browe/great3/beta/truth",
        file_prefixes=("galaxy_catalog",), suffixes=("",), make_plots=False, logger=logger)

    # Then get the submission truth
    idt, xt, yt, g1t, g2t = get_variable_gsuffix(
        "control", "space", suffix="", file_prefix="galaxy_catalog",
        test_dir="/Users/browe/great3/beta/truth") # True = g1/g2 only
    ret = make_fits_cats(idt, g1t, g2t, prefix="gtrue_comparison")
    gtruesubfile = "./submissions/gtrue_comparison_csv.asc"
    call_list = [
        "./presubmission_alpha-2", "-b", "control-space-variable",
        "-o", gtruesubfile, ]+glob.glob("./cats/gtrue_comparison-*")
    subprocess.check_call(call_list)
    subdata = np.loadtxt(gtruesubfile)
    fields, thetas, map_Es, map_Bs, maperrs = (
        subdata[:, 0], subdata[:, 1], subdata[:, 2], subdata[:, 3], subdata[:, 4])

#    print thetat - thetas

    import matplotlib.pyplot as plt
    for theta, diff, mapE in zip(
        np.split(thetat, evaluate.NFIELDS), np.split(map_Et - map_Es, evaluate.NFIELDS), 
        np.split(map_Et, evaluate.NFIELDS)):

        plt.loglog(theta, np.abs(diff) / np.abs(mapE), '--')

    plt.title("Abs(map_E_truth - map_E_truth_presub) / Abs(map_E_truth)")
    plt.savefig("fractional_mapdiff.png")
    plt.clf()
    for theta, diff, mapE in zip(
        np.split(thetat, evaluate.NFIELDS), np.split(map_Et - map_Es, evaluate.NFIELDS), 
        np.split(map_Et, evaluate.NFIELDS)):

        plt.loglog(theta, np.abs(diff), '--')

    plt.title("Abs(map_E_truth - map_E_presub)")
    plt.savefig("absolute_ediff.png")
 
    print map_Et - map_Es
 
