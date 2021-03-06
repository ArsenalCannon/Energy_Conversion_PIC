"""
Analysis procedures for particle energy spectrum fitting.
"""
import collections
import math
import os.path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import rc
from scipy.optimize import curve_fit

import color_maps as cm
import colormap.colormaps as cmaps
import fitting_funcs
import palettable
import pic_information
from energy_conversion import read_data_from_json
from runs_name_path import *
from shell_functions import mkdir_p

rc('font', **{'family': 'serif', 'serif': ['Computer Modern']})
mpl.rc('text', usetex=True)
mpl.rcParams['text.latex.preamble'] = [r"\usepackage{amsmath}"]

colors = palettable.colorbrewer.qualitative.Set1_9.mpl_colors

font = {
    'family': 'serif',
    #'color'  : 'darkred',
    'color': 'black',
    'weight': 'normal',
    'size': 24,
}


def accumulated_particle_info(ene, f):
    """
    Get the accumulated particle number and total energy from
    the distribution function.

    Args:
        ene: the energy bins array.
        f: the energy distribution array.
    Returns:
        nacc_ene: the accumulated particle number with energy.
        eacc_ene: the accumulated particle total energy with energy.
    """
    nbins, = f.shape
    dlogE = (math.log10(max(ene)) - math.log10(min(ene))) / nbins
    nacc_ene = np.zeros(nbins)
    eacc_ene = np.zeros(nbins)
    nacc_ene[0] = f[0] * ene[0]
    eacc_ene[0] = 0.5 * f[0] * ene[0]**2
    for i in range(1, nbins):
        nacc_ene[i] = f[i] * (ene[i] + ene[i - 1]) * 0.5 + nacc_ene[i - 1]
        eacc_ene[i] = 0.5 * f[i] * (ene[i] - ene[i - 1]) * (
            ene[i] + ene[i - 1])
        eacc_ene[i] += eacc_ene[i - 1]
    nacc_ene *= dlogE
    eacc_ene *= dlogE
    return (nacc_ene, eacc_ene)


def get_thermal_total(ene, f, fthermal, fnorm):
    """Get total and thermal particle number and energy.

    Args:
        ene: the energy bins array.
        f: the particle energy distribution array.
        fthermal: thermal part of the particle distribution.
        fnorm: normalization value for f.

    Returns:
        nthermal: particle number of thermal part.
        ntot: total particle number.
        ethermal: particle kinetic energy of thermal part.
        etot: total particle kinetic energy.
    """
    nacc, eacc = accumulated_particle_info(ene, f)
    ntot = nacc[-1]
    etot = eacc[-1]
    nacc_thermal, eacc_thermal = accumulated_particle_info(ene, fthermal)
    nthermal = nacc_thermal[-1]
    ethermal = eacc_thermal[-1]
    nthermal *= fnorm
    ethermal *= fnorm
    ntot *= fnorm
    etot *= fnorm
    print 'Thermal and total particles: ', nthermal, ntot, nthermal / ntot
    print 'Thermal and total energies: ', ethermal, etot, ethermal / etot
    print '---------------------------------------------------------------'
    return (nthermal, ntot, ethermal, etot)


def fit_thermal_core(ene, f):
    """Fit to get the thermal core of the particle distribution.

    Fit the thermal core of the particle distribution.
    The thermal core is fitted as a Maxwellian distribution.

    Args:
        ene: the energy bins array.
        f: the particle flux distribution.

    Returns:
        fthermal: thermal part of the particle distribution.
    """
    print 'Fitting to get the thermal core of the particle distribution.'
    estart = 0
    ng = 3
    kernel = np.ones(ng) / float(ng)
    fnew = np.convolve(f, kernel, 'same')
    nshift = 10  # grids shift for fitting thermal core.
    eend = np.argmax(fnew) + nshift
    popt, pcov = curve_fit(fitting_funcs.func_maxwellian, ene[estart:eend],
                           f[estart:eend])
    fthermal = fitting_funcs.func_maxwellian(ene, popt[0], popt[1])
    print 'Energy with maximum flux: ', ene[eend - 10]
    print 'Energy with maximum flux in fitted thermal core: ', 0.5 / popt[1]
    print 'Thermal core fitting coefficients: '
    print popt
    print '---------------------------------------------------------------'
    return fthermal


def background_thermal_core(ene, f, vth, mime):
    """Fit background thermal core.

    Fit the background thermal core of the particle distribution. The
    background will be far away from the current sheet, so we don't have to
    consider the drift velocities. The thermal energy is calculated from
    the initial thermal velocity.

    Args:
        ene: the energy bins array.
        f: the particle flux distribution.
        vth: thermal speed.
        mime: mass ratio

    Returns:
        fthermal: thermal part of the particle distribution.
    """
    print('Fitting background thermal core')
    gama = 1.0 / math.sqrt(1.0 - 3.0 * vth**2)
    thermalEnergy = (gama - 1) * mime
    fthermal = fitting_funcs.func_maxwellian(ene, 1.0, 1.5 / thermalEnergy)
    nanMinIndex = np.nanargmin(f / fthermal)
    tindex = np.argmin(f[:nanMinIndex] / fthermal[:nanMinIndex])
    fthermal *= f[tindex] / fthermal[tindex]
    #fthermal *= f[0]/fthermal[0]
    print('---------------------------------------------------------------')
    return fthermal


def lower_thermal_core(ene, f):
    """Fit the thermal core with lower particle energy.

    Fit the thermal core with lower energy, which is not supposed to be
    in the non-thermal particles.

    Args:
        ene: the energy bins array.
        f: the particle flux distribution, which is the original particle
            distribution subtracted by the background plasma.

    Returns:
        fthermal: thermal part of the particle distribution f.
    """
    print('Fitting lower energy thermal core...')
    estart = 0
    eend = np.argmax(f)
    emin = np.argmin(f[:eend])
    popt, pcov = curve_fit(fitting_funcs.func_maxwellian, ene[estart:emin],
                           f[estart:emin])
    fthermal = fitting_funcs.func_maxwellian(ene, popt[0], popt[1])
    fthermal[:emin] += f[:emin] - fthermal[:emin]
    fthermal[emin:] = 0.0
    print 'Lower thermal core fitting coefficients: '
    print popt
    print('---------------------------------------------------------------')
    return fthermal


def fit_nonthermal_power_law(ene, f, fthermal, species, eshift, erange):
    """Power-law fitting for nonthermal particles.

    Using a linear function to fit for reducing fitting error.
    If f = b * x^a, log(f) = log(b) + a*log(x)

    Args:
        ene: the energy bins array.
        f: the particle flux array.
        fthermal: thermal part of the particle distribution.
        species: particle species. 'e' for electron, 'h' for ion.
        eshift: the shift from the maximum of the nonthermal distribution.
        erange: the energy bins of the part for fitting.

    Returns:
        fpowerlaw: the power-law fitting of the non-thermal part of the
            particle distribution.
        e_start, e_end: the starting and ending energy bin index for fitting.
        popt: the fitting parameters.
    """
    fnonthermal = f - fthermal
    estart = np.argmax(fnonthermal) + eshift
    eend = estart + erange
    popt, pcov = curve_fit(fitting_funcs.func_line,
                           np.log10(ene[estart:eend]),
                           np.log10(fnonthermal[estart:eend]))
    print 'Starting and ending energies for fitting: ', ene[estart], ene[eend]
    print '---------------------------------------------------------------'
    fpowerlaw = fitting_funcs.func_line(np.log10(ene), popt[0], popt[1])
    fpowerlaw = np.power(10, fpowerlaw)
    return (fpowerlaw, estart, eend, popt)


def fit_powerlaw_whole(ene, f, species):
    """Power-law fitting for the high energy part of the whole spectrum.

    Args:
        ene: the energy bins array.
        f: the particle flux array.
        species: particle species. 'e' for electron, 'h' for ion.

    Returns:
        fpower: the power-law fitting of the non-thermal part of the
            particle distribution.
    """
    estart = np.argmax(f) + 50
    print "Energy bin index with maximum flux: ", np.argmax(f)
    if (species == 'e'):
        power_range = 90  # for electrons
    else:
        power_range = 130  # for ions
    eend = estart + power_range
    popt, pcov = curve_fit(fitting_funcs.func_line,
                           np.log10(ene[estart:eend]),
                           np.log10(f[estart:eend]))
    print 'Starting and ending energies for fitting: ', ene[estart], ene[eend]
    print 'Power-law fitting coefficients for all particles: '
    print popt
    print '---------------------------------------------------------------'
    fpower = fitting_funcs.func_line(np.log10(ene), popt[0], popt[1])
    fpower = np.power(10, fpower)
    npower, epower = accumulated_particle_info(ene[estart:eend],
                                               fpower[estart:eend])
    ntot, etot = accumulated_particle_info(ene, f)
    nportion = npower[-1] / ntot[-1]
    eportion = epower[-1] / etot[-1]
    return (fpower, estart, eend, popt, nportion, eportion)


def plot_spectrum(ct, species, ax, pic_info, **kwargs):
    """Plotting the energy spectrum.
    Args:
        ct: the time point index.
        species: particle species. 'e' for electron, 'h' for ion.
        pic_info: namedtuple for the PIC simulation information.
        ax: axes object for the plot.
    """
    if "fpath" in kwargs:
        fpath = kwargs["fpath"]
    else:
        fpath = '../spectrum/'
    fname = fpath + "spectrum-" + species + "." + str(ct)
    fnorm = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
    if (os.path.isfile(fname)):
        elin, flin, elog, flog = get_energy_distribution(fname, fnorm)
    else:
        print "ERROR: the spectrum data file doesn't exist."
        return
    # Ions have lower Lorentz factor due to higher mass
    if (species == 'h'):
        flog /= pic_info.mime
    elog_norm = get_normalized_energy(species, elog, pic_info)
    ps = []
    p1, = ax.loglog(elog, flog, linewidth=2)
    if "color" in kwargs:
        p1.set_color(kwargs["color"])
    ps.append(p1)

    color = p1.get_color()
    fthermal = fit_thermal_core(elog, flog)
    fnonthermal = flog - fthermal
    fthermal1 = fit_thermal_core(elog, fnonthermal)
    fnonthermal1 = fnonthermal - fthermal1
    get_thermal_total(elog, flog, fthermal, fnorm)
    ax.loglog(
        elog,
        fthermal1,
        linewidth=2,
        color='k',
        linestyle='--',
        label='Thermal')
    # Plot thermal core
    if "is_thermal" in kwargs and kwargs["is_thermal"] == True:
        p2, = ax.loglog(
            elog,
            fthermal,
            linewidth=2,
            color='k',
            linestyle='--',
            label='Thermal')
        if species == 'e':
            p2, = ax.loglog(
                elog[270:],
                fnonthermal[270:],
                linewidth=2,
                color='b',
                linestyle='--',
                label='Thermal')
        else:
            p2, = ax.loglog(
                elog[100:],
                fnonthermal[100:],
                linewidth=2,
                color='b',
                linestyle='--',
                label='Thermal')
        ps.append(p2)
    # Plot Power-law spectrum
    if "is_power" in kwargs and kwargs["is_power"] == True:
        offset = kwargs["offset"]
        extent = kwargs["extent"]
        power_fit = power_law_fit(elog, fnonthermal, offset, extent)
        es, ee = power_fit.es, power_fit.ee
        fpower = power_fit.fpower
        powerIndex = "{%0.2f}" % power_fit.params[0]
        pname = '$\sim E^{' + powerIndex + '}$'
        es -= e_extend
        ee += e_extend
        p3, = ax.loglog(
            elog_norm[es:ee],
            fpower[es:ee] * 2,
            color=color,
            linestyle='--',
            linewidth=2,
            label=pname)
        ps.append(p3)

    if "xlim" in kwargs:
        ax.set_xlim(kwargs["xlim"])
    if "ylim" in kwargs:
        ax.set_ylim(kwargs["ylim"])


def plot_powerlaw_whole(ene, fpower_whole, es, ee, popt, color):
    """Plot power-law fitted spectrum for the overall spectrum.

    Args:
        ene: the energy bins array.
        f: the particle flux array.
        fpower_whole: the fitted power-law spectrum.
        es, ee: the starting and ending energy bin index for fitting.
        popt: the fitting parameters.
        color: color to plot the line.

    """
    powerIndex = "{%0.2f}" % popt[0]
    # powerIndex = str(-1)
    pname = '$\sim E^{' + powerIndex + '}$'
    shift = 40
    p1, = plt.loglog(
        ene[es - shift:ee + shift + 1],
        fpower_whole[es - shift:ee + shift + 1] * 4,
        linewidth=2,
        linestyle='--',
        color=color,
        label=pname)
    plt.text(30, 8, pname, color=color, rotation=-0, fontsize=20)


def get_normalized_energy(species, ene_bins, pic_info):
    """Normalize the energies to the initial thermal energy

    Args:
        species: particle species. 'e' for electron, 'h' for ion.
        ene_bins: the energy bins.
    """
    if (species == 'e'):
        vth = pic_info.vthe
    else:
        vth = pic_info.vthi
    print vth
    gama = 1.0 / math.sqrt(1.0 - 3.0 * vth**2)
    eth = gama - 1.0
    ene_bins_norm = ene_bins / eth
    return ene_bins_norm


def get_energy_distribution(fname, fnorm):
    """ Get energy bins and corresponding particle flux.

    Get linear and logarithm energy bins and particle flux.

    Args:
        fname: file name.
        fnorm: normalization for the distribution.

    Returns:
        ene_lin: linear scale of energy bins.
        ene_log: logarithm scale of energy bins.
        flin: particle flux corresponding to ene_lin.
        flog: particle flux corresponding to ene_log.
    """
    data = read_spectrum_data(fname)
    ene_lin = data[:, 0]  # Linear scale energy bins
    flin = data[:, 1]  # Flux using linear energy bins
    print 'Total number of particles: ', sum(flin)  # Total number of electrons
    print 'Normalization of the energy distribution: ', fnorm

    ene_log = data[:, 2]  # Logarithm scale energy bins
    flog = data[:, 3]  # Flux using Logarithm scale bins
    flog /= fnorm  # Normalized by the maximum value.
    return (ene_lin, flin, ene_log, flog)


def plot_spectrum_bulk(ntp, species, pic_info):
    """Plot a series of energy spectra at bulk energy decay time.

    Args:
        ntp: total number of time frames.
        species: particle species. 'e' for electron, 'h' for ion.
        pic_info: namedtuple for the PIC simulation information.
    """
    fig, ax = plt.subplots(figsize=[7, 5])
    for current_time in range(1, ntp - 1, 2):
        plot_spectrum(current_time, species, pic_info, ax, False, False)
    plot_spectrum(ntp, species, pic_info, ax, True, False)

    if (species == 'e'):
        vth = pic_info.vthe
    else:
        vth = pic_info.vthi
    gama = 1.0 / math.sqrt(1.0 - 3 * vth**2)
    eth = gama - 1.0
    fname = "../spectrum/whole/spectrum-" + species + \
            "." + str(1).zfill(len(str(1)))
    nx = pic_info.nx
    ny = pic_info.ny
    nz = pic_info.nz
    nppc = pic_info.nppc
    fnorm = nx * ny * nz * nppc
    ene_lin, flin, ene_log, flog = get_energy_distribution(fname, fnorm)
    ene_log_norm = get_normalized_energy(species, ene_log, pic_info)

    f_intial = fitting_funcs.func_maxwellian(ene_log, fnorm, 1.5 / eth)
    nacc_ene, eacc_ene = accumulated_particle_info(ene_log, f_intial)
    p41, = ax.loglog(
        ene_log_norm,
        f_intial / nacc_ene[-1],
        linewidth=2,
        color='k',
        linestyle='--',
        label=r'Initial')
    ax.set_xlabel('$E/E_{th}$', fontdict=font)
    ax.set_ylabel('$f(E)/N_0$', fontdict=font)
    ax.tick_params(labelsize=20)
    plt.tight_layout()
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    fig.savefig('../img/spect_time.eps')
    plt.show()


def plot_spectrum_bulk(ntp, species, pic_info):
    """Plot a series of energy spectra at bulk energy decay time.

    Args:
        ntp: total number of time frames.
        species: particle species. 'e' for electron, 'h' for ion.
        pic_info: namedtuple for the PIC simulation information.
    """
    fig, ax = plt.subplots(figsize=[7, 5])
    # ax.set_color_cycle(palettable.colorbrewer.qualitative.Accent_6.mpl_colors)
    # colors = palettable.colorbrewer.qualitative.Accent_6.mpl_colors
    colors = ['b', 'g', 'r', 'c', 'm', 'y']
    ax.set_color_cycle(colors)
    dtp = int(pic_info.dt_particles) + 1
    i = 0
    for ct in range(2, 8):
        plot_spectrum(ct, species, pic_info, ax, False, False)
        tname = str(dtp * ct) + '$\Omega_{ci}^{-1}$'
        ys = 0.6 - 0.1 * i
        ax.text(
            0.05,
            ys,
            tname,
            color=colors[i],
            fontsize=20,
            horizontalalignment='left',
            verticalalignment='center',
            transform=ax.transAxes)
        i += 1

    ax.set_xlabel('$E/E_{th}$', fontdict=font)
    ax.set_ylabel('$f(E)$', fontdict=font)
    ax.tick_params(labelsize=20)
    plt.tight_layout()
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    fname = 'spect_time_bulk_' + species + '.eps'
    fig.savefig('../img/' + fname)
    plt.show()


def read_spectrum_data(fname):
    """Read particle energy spectrum data.

    Read particle energy spectrum data at time point it from file.

    Args:
        fname: the file name of the energy spectrum.

    Returns:
        data: the energy bins data and corresponding flux.
            Linear bin + Linear flux + Logarithm bins + Logarithm flux
    """
    try:
        f = open(fname, 'r')
    except IOError:
        print "cannot open ", fname
    else:
        data = np.genfromtxt(f, delimiter='')
        f.close()
        return data


def maximum_energy_spectra(ntp, species, pic_info, fpath='../spectrum/'):
    """Get the maximum energy from a energy spectra.

    Args:
        ntp: total number of time frames.
        species: particle species. 'e' for electron, 'h' for ion.
        pic_info: namedtuple for the PIC simulation information.
        fpath: the file path for the spectra data.
    Return:
        max_ene: the maximum energy at each time step.
    """
    max_ene = np.zeros(ntp)
    for ct in range(1, ntp, 1):
        # Get particle spectra energy bins and flux
        fname = fpath + "spectrum-" + species + "." + str(ct).zfill(
            len(str(ct)))
        nx = pic_info.nx
        ny = pic_info.ny
        nz = pic_info.nz
        nppc = pic_info.nppc
        if species == 'e':
            ptl_mass = 1.0
        else:
            ptl_mass = pic_info.mime
        fnorm = nx * ny * nz * nppc * ptl_mass
        if (os.path.isfile(fname)):
            ene_lin, flin, ene_log, flog = get_energy_distribution(fname,
                                                                   fnorm)
        else:
            print "ERROR: the spectrum data file doesn't exist."
            return
        ene_log_norm = get_normalized_energy(species, ene_log, pic_info)
        max_ene[ct] = ene_log[np.max(np.nonzero(flog))]

    if (species == 'e'):
        vth = pic_info.vthe
    else:
        vth = pic_info.vthi
    gama = 1.0 / math.sqrt(1.0 - 3 * vth**2)
    eth = gama - 1.0

    return max_ene / eth


def maximum_energy_particle(species, pic_info, fpath='../spectrum/'):
    """Get the actual maximum energy from particle data

    Args:
        species: particle species. 'e' for electron, 'h' for ion.
        pic_info: namedtuple for the PIC simulation information.
        fpath: the file path for the spectra data.
    Return:
        max_ene: the maximum energy at each time step.
    """
    max_ene = np.zeros(pic_info.ntp)
    fname = fpath + "emax-" + species + ".dat"
    with open(fname, 'r') as f:
        max_ene = np.genfromtxt(f)
    if (species == 'e'):
        vth = pic_info.vthe
    else:
        vth = pic_info.vthi
    gama = 1.0 / math.sqrt(1.0 - 3 * vth**2)
    eth = gama - 1.0

    return max_ene / eth


def plot_maximum_energy(pic_info, dir):
    """Plot a series of energy spectra.

    Args:
        pic_info: namedtuple for the PIC simulation information.
        dir: the directory that contains the particle spectra data.
    """
    max_ene_e = maximum_energy_particle('e', pic_info, dir)
    max_ene_i = maximum_energy_particle('h', pic_info, dir)

    fig = plt.figure(figsize=[7, 5])
    width = 0.69
    height = 0.8
    xs = 0.16
    ys = 0.95 - height
    ax = fig.add_axes([xs, ys, width, height])
    tparticles = pic_info.tparticles
    ntp, = tparticles.shape
    nt1, = max_ene_e.shape
    nt = min(nt1, ntp)
    p1 = ax.plot(tparticles[:nt], max_ene_e[:nt], color=colors[0], linewidth=2)
    ax.set_xlabel('$t\Omega_{ci}$', fontdict=font)
    ax.set_ylabel(
        r'$\varepsilon_\text{emax}/\varepsilon_\text{the}$',
        fontdict=font,
        color=colors[0])
    for tl in ax.get_yticklabels():
        tl.set_color(colors[0])
    ax.tick_params(labelsize=20)
    ax1 = ax.twinx()
    p2 = ax1.plot(
        tparticles[:nt], max_ene_i[:nt], color=colors[1], linewidth=2)
    ax1.tick_params(labelsize=20)
    ax1.set_ylabel(
        r'$\varepsilon_\text{imax}/\varepsilon_\text{thi}$',
        fontdict=font,
        color=colors[1])
    for tl in ax1.get_yticklabels():
        tl.set_color(colors[1])
    # plt.show()


def move_energy_spectra():
    if not os.path.isdir('../data/'):
        os.makedirs('../data/')
    fdir = '../data/spectra/'
    if not os.path.isdir(fdir):
        os.makedirs(fdir)
    # base_dirs, run_names = ApJ_long_paper_runs()
    # base_dirs, run_names = guide_field_runs()
    base_dirs, run_names = low_beta_runs()
    for base_dir, run_name in zip(base_dirs, run_names):
        fpath = fdir + run_name
        if not os.path.isdir(fpath):
            os.makedirs(fpath)
        fname = base_dir + "/pic_analysis/spectrum/*"
        if os.path.isfile(fname):
            command = "cp " + fname + " " + fpath
        else:
            fname = base_dir + "/spectrum*"
            command = "cp " + fname + " " + fpath

        os.system(command)


def plot_nonthernal_fraction(nnth, enth, pic_info):
    """Plot nonthermal fractions for particle number and energy.

    Args:
        nnth: nonthermal fraction for particle number.
        enth: nonthermal fraction for particle energy.
        pic_info: particle information namedtuple.
    """
    tptl = np.zeros(pic_info.ntp + 1)
    tptl[1:] = pic_info.tparticles + pic_info.dt_particles
    nt = min(tptl.shape, len(nnth))
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.13, 0.13
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    p1, = ax.plot(
        tptl[:nt], nnth[:nt], linewidth=2, label=r'$N_\text{nth}/N_0$')
    p2, = ax.plot(
        tptl[:nt],
        enth[:nt],
        linewidth=2,
        label=r'$\varepsilon_\text{nth}/\varepsilon_\text{tot}$')
    ax.set_xlim([0, np.max(tptl)])
    ax.set_ylim([0, 1.0])

    ax.set_xlabel(r'$t\Omega_{ci}$', fontdict=font, fontsize=24)
    ax.set_ylabel(r'Non-thermal fraction', fontdict=font, fontsize=24)
    ax.tick_params(labelsize=20)
    leg = ax.legend(
        loc=4,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    for color, text in zip(colors, leg.get_texts()):
        text.set_color(color)


def calc_nonthermal_fraction(species):
    """Calculate nonthermal fraction.

    Args:
        species: particle species.
    """
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/nonthermal/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    # base_dirs, run_names = ApJ_long_paper_runs()
    base_dirs, run_names = guide_field_runs()
    nruns = len(run_names)
    nnth_fraction = []
    enth_fraction = []
    for run_name in run_names:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        ct = 1
        fname = dir + 'spectrum-' + species + '.1'
        file_exist = os.path.isfile(fname)
        nnth_time = [0]
        enth_time = [0]
        while file_exist:
            elin, flin, elog, flog = get_energy_distribution(fname, n0)
            ct += 1
            fname = dir + 'spectrum-' + species + '.' + str(ct)
            file_exist = os.path.isfile(fname)
            fthermal = fit_thermal_core(elog, flog)
            fnonthermal = flog - fthermal
            ntot, etot = accumulated_particle_info(elog, flog)
            nnth, enth = accumulated_particle_info(elog, fnonthermal)
            nnth_time.append(nnth[-1] / ntot[-1])
            enth_time.append(enth[-1] / etot[-1])
        plot_nonthernal_fraction(nnth_time, enth_time, pic_info)
        fname = img_dir + 'nth_' + run_name + '_' + species + '.eps'
        plt.savefig(fname)
        plt.close()
        nnth_fraction.append(nnth[-1] / ntot[-1])
        enth_fraction.append(enth[-1] / etot[-1])
    for i in range(nruns):
        print("%s %5.2f %5.2f" % (run_names[i], nnth_fraction[i],
                                  enth_fraction[i]))

    return (nnth_fraction, enth_fraction)


def power_law_fit(ene, f, offset, extend):
    """Power-law fitting for the power-law part of the spectrum.

    Args:
        ene: the energy bins array.
        f: the particle flux array.
        species: particle species. 'e' for electron, 'h' for ion.
        offset: offset energy bins from the energy with the maximum f.
        extend: the extend of the power-law part.

    Returns:
        fpower: the power-law fitting of the non-thermal part of the
            particle distribution.
    """
    estart = np.argmax(f) + offset
    print("Energy bin index with maximum flux: %d" % np.argmax(f))
    eend = estart + extend
    popt, pcov = curve_fit(fitting_funcs.func_line,
                           np.log10(ene[estart:eend]),
                           np.log10(f[estart:eend]))
    print 'Starting and ending energies for fitting: ', ene[estart], ene[eend]
    print 'Power-law fitting coefficients for all particles: '
    print popt
    print '---------------------------------------------------------------'
    fpower = fitting_funcs.func_line(np.log10(ene), popt[0], popt[1])
    fpower = np.power(10, fpower)
    npower, epower = accumulated_particle_info(ene[estart:eend],
                                               fpower[estart:eend])
    ntot, etot = accumulated_particle_info(ene, f)
    nfraction = npower[-1] / ntot[-1]
    efraction = epower[-1] / etot[-1]
    power_fitting = collections.namedtuple(
        "power_fitting",
        ['fpower', 'es', 'ee', 'params', 'nfraction', 'efraction'])
    power_fit = power_fitting(
        fpower=fpower,
        es=estart,
        ee=eend,
        params=popt,
        nfraction=nfraction,
        efraction=efraction)
    return power_fit


def plot_spectra_beta_electron():
    """Plot spectra for multiple runs with different beta.

    """
    species = 'e'
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/spectra/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.15, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    base_dirs, run_names = ApJ_long_paper_runs()
    nruns = len(run_names)
    shift = 1
    offset = [50, 80, 50, 50]
    extent = [10, 40, 100, 110]
    run = 0
    e_extend = 20
    colors_plot = []
    for run_name in run_names[:4]:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        ct = 1
        fname = dir + 'spectrum-' + species + '.1'
        file_exist = os.path.isfile(fname)
        while file_exist:
            ct += 1
            fname = dir + 'spectrum-' + species + '.' + str(ct)
            file_exist = os.path.isfile(fname)
        fname = dir + 'spectrum-' + species + '.' + str(ct - 1)
        elin, flin, elog, flog = get_energy_distribution(fname, n0)
        elog_norm = get_normalized_energy(species, elog, pic_info)
        flog *= shift
        # p1, = ax.loglog(elog_norm, flog, linewidth=2)
        p1, = ax.semilogy(elog_norm, flog, linewidth=2)
        power_fit = power_law_fit(elog, flog, offset[run], extent[run])
        es, ee = power_fit.es, power_fit.ee
        fpower = power_fit.fpower
        color = p1.get_color()
        es -= e_extend
        ee += e_extend
        powerIndex = "{%0.2f}" % power_fit.params[0]
        pname = r'$\sim \varepsilon^{' + powerIndex + '}$'
        if run > 0:
            p23, = ax.loglog(
                elog_norm[es:ee],
                fpower[es:ee] * 2,
                color=color,
                linestyle='--',
                linewidth=2,
                label=pname)
            # p23, = ax.semilogy(elog_norm[es:ee], fpower[es:ee]*2, color=color,
            #         linestyle='--', linewidth=2, label=pname)
            colors_plot.append(color)
        # # Help for fitting
        # p21, = ax.loglog(elog_norm[es], flog[es], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p22, = ax.loglog(elog_norm[ee], flog[ee], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p23, = ax.loglog(elog_norm, fpower)
        ax.set_xlim([1E-1, 2E3])
        # ax.set_xlim([1E-3, 1E3])
        ax.set_ylim([1E-5, 1E4])
        shift *= 5
        run += 1

    ax.set_xlabel(
        r'$\varepsilon/\varepsilon_\text{th}$', fontdict=font, fontsize=24)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font, fontsize=24)
    ax.tick_params(labelsize=20)
    leg = ax.legend(
        loc=3,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    for color, text in zip(colors_plot, leg.get_texts()):
        text.set_color(color)
    ax.text(
        0.5,
        0.05,
        'R8',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.6,
        0.05,
        'R7',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.7,
        0.05,
        'R1',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.85,
        0.05,
        'R6',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)

    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    dir = '../img/spectra/'
    if not os.path.isdir(dir):
        os.makedirs(dir)
    fname = dir + 'spect_beta_electron.eps'
    fig.savefig(fname, transparent=True)

    plt.show()


def plot_spectra_beta_electron_fitted():
    """Plot spectra for multiple runs with different beta.

    """
    species = 'e'
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/spectra/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.15, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    base_dirs, run_names = ApJ_long_paper_runs()
    nruns = len(run_names)
    shift = 1
    offset = [50, 90, 20, 25]
    extent = [10, 30, 45, 50]
    shift = [1, 5, 25, 125]
    run = 0
    e_extend = 20
    colors_plot = []
    e_nth = 200
    # run = 3
    for run_name in run_names[:4]:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        ct = 1
        fname = dir + 'spectrum-' + species + '.1'
        file_exist = os.path.isfile(fname)
        while file_exist:
            ct += 1
            fname = dir + 'spectrum-' + species + '.' + str(ct)
            file_exist = os.path.isfile(fname)
        fname = dir + 'spectrum-' + species + '.' + str(ct - 1)
        elin, flin, elog, flog = get_energy_distribution(fname, n0)
        elog_norm = get_normalized_energy(species, elog, pic_info)
        flog *= shift[run]
        fthermal = fit_thermal_core(elog, flog)
        fnonthermal = flog - fthermal
        p1, = ax.loglog(elog_norm, flog, linewidth=2)
        color = p1.get_color()
        if run > 0:
            p11, = ax.loglog(
                elog_norm[e_nth:], fnonthermal[e_nth:], color=color)

        if run < 2:
            power_fit = power_law_fit(elog, flog, offset[run], extent[run])
        else:
            power_fit = power_law_fit(elog, fnonthermal, offset[run],
                                      extent[run])
        # power_fit = power_law_fit(elog, flog, 90, 30)
        # power_fit = power_law_fit(elog, fnonthermal, 35, 70)
        es, ee = power_fit.es, power_fit.ee
        fpower = power_fit.fpower
        es -= e_extend
        ee += e_extend
        powerIndex = "{%0.2f}" % power_fit.params[0]
        pname = r'$\sim \varepsilon^{' + powerIndex + '}$'
        if run > 0:
            p23, = ax.loglog(
                elog_norm[es:ee],
                fpower[es:ee] * 2,
                color=color,
                linestyle='--',
                linewidth=2,
                label=pname)
            colors_plot.append(color)
        # # Help for fitting
        # p21, = ax.loglog(elog_norm[es], flog[es], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p22, = ax.loglog(elog_norm[ee], flog[ee], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p21, = ax.loglog(elog_norm[es], fnonthermal[es], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p22, = ax.loglog(elog_norm[ee], fnonthermal[ee], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p23, = ax.loglog(elog_norm, fpower)
        ax.set_xlim([1E-1, 2E3])
        ax.set_ylim([1E-5, 1E4])
        # shift *= 5
        run += 1

    ax.set_xlabel(
        r'$\varepsilon/\varepsilon_\text{th}$', fontdict=font, fontsize=24)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font, fontsize=24)
    ax.tick_params(labelsize=20)
    leg = ax.legend(
        loc=3,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    for color, text in zip(colors_plot, leg.get_texts()):
        text.set_color(color)
    ax.text(
        0.50,
        0.05,
        'R8',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.59,
        0.05,
        'R7',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.7,
        0.05,
        'R1',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.85,
        0.05,
        'R6',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.5,
        0.27,
        r'$\beta_e=0.2$',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes,
        rotation=-75)
    ax.text(
        0.6,
        0.25,
        r'$\beta_e=0.07$',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes,
        rotation=-75)
    ax.text(
        0.7,
        0.25,
        r'$\beta_e=0.02$',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes,
        rotation=-68)
    ax.text(
        0.82,
        0.25,
        r'$\beta_e=0.007$',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes,
        rotation=-62)

    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    dir = '../img/spectra/'
    if not os.path.isdir(dir):
        os.makedirs(dir)
    fname = dir + 'spect_beta_electron_fitted.eps'
    fig.savefig(fname)

    plt.show()


def plot_spectra_multi_electron():
    """Plot spectra for multiple runs with the same beta for electron.

    """
    species = 'e'
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/spectra/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.15, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    base_dirs, run_names = ApJ_long_paper_runs()
    nruns = len(run_names)
    shift = 1
    offset = [80, 65, 65, 65]
    extent = [40, 60, 70, 60]
    shift = [0.1, 10, 4, 1]
    run = 0
    e_extend = 40
    colors_plot = []
    for run_name in run_names[4:8]:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        ct = 1
        fname = dir + 'spectrum-' + species + '.1'
        file_exist = os.path.isfile(fname)
        while file_exist:
            ct += 1
            fname = dir + 'spectrum-' + species + '.' + str(ct)
            file_exist = os.path.isfile(fname)
        fname = dir + 'spectrum-' + species + '.' + str(ct - 1)
        elin, flin, elog, flog = get_energy_distribution(fname, n0)
        elog_norm = get_normalized_energy(species, elog, pic_info)
        flog *= shift[run]
        p1, = ax.loglog(elog_norm, flog, linewidth=2)
        power_fit = power_law_fit(elog, flog, offset[run], extent[run])
        es, ee = power_fit.es, power_fit.ee
        fpower = power_fit.fpower
        color = p1.get_color()
        es -= e_extend
        ee += e_extend
        powerIndex = "{%0.2f}" % power_fit.params[0]
        pname = r'$\sim \varepsilon^{' + powerIndex + '}$'
        p23, = ax.loglog(
            elog_norm[es:ee],
            fpower[es:ee] * 2,
            color=color,
            linestyle='--',
            linewidth=2,
            label=pname)
        colors_plot.append(color)
        # Help for fitting
        p21, = ax.loglog(
            elog_norm[es],
            flog[es],
            marker='.',
            markersize=10,
            linestyle='None',
            color=color)
        p22, = ax.loglog(
            elog_norm[ee],
            flog[ee],
            marker='.',
            markersize=10,
            linestyle='None',
            color=color)
        p23, = ax.loglog(elog_norm, fpower)
        ax.set_xlim([1E-1, 3E2])
        ax.set_ylim([1E-5, 1E4])
        shift *= 5
        run += 1

    ax.set_xlabel(
        r'$\varepsilon/\varepsilon_\text{th}$', fontdict=font, fontsize=24)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font, fontsize=24)
    ax.tick_params(labelsize=20)
    leg = ax.legend(
        loc=3,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    for color, text in zip(colors_plot, leg.get_texts()):
        text.set_color(color)
    ax.text(
        0.05,
        0.66,
        'R5',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.9,
        'R3',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.82,
        'R2',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.76,
        'R4',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)

    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    dir = '../img/spectra/'
    if not os.path.isdir(dir):
        os.makedirs(dir)
    fname = dir + 'spect_multi_electron.eps'
    fig.savefig(fname)

    plt.show()


def plot_spectra_multi_electron_fitted():
    """Plot spectra for multiple runs with the same beta for electron.

    """
    species = 'e'
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/spectra/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.15, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    base_dirs, run_names = ApJ_long_paper_runs()
    nruns = len(run_names)
    shift = 1
    offset = [15, 15, 15, 15]
    extent = [40, 40, 40, 40]
    shift = [1, 1, 20, 400]
    run = 0
    e_extend = 20
    colors_plot = []
    e_nth = [400, 300, 350, 400]
    ng = 3
    kernel = np.ones(ng) / float(ng)
    for run_name in run_names[4:8]:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        ct = 1
        fname = dir + 'spectrum-' + species + '.1'
        file_exist = os.path.isfile(fname)
        while file_exist:
            ct += 1
            fname = dir + 'spectrum-' + species + '.' + str(ct)
            file_exist = os.path.isfile(fname)
        fname = dir + 'spectrum-' + species + '.' + str(ct - 1)
        elin, flin, elog, flog = get_energy_distribution(fname, n0)
        elog_norm = get_normalized_energy(species, elog, pic_info)
        flog *= shift[run]
        flog = np.convolve(flog, kernel, 'same')
        fthermal = fit_thermal_core(elog, flog)
        fnonthermal = flog - fthermal
        p1, = ax.loglog(elog_norm, flog, linewidth=2)
        color = p1.get_color()
        p11, = ax.loglog(
            elog_norm[e_nth[run]:], fnonthermal[e_nth[run]:], color=color)
        # power_fit = power_law_fit(elog, fnonthermal, 310, 50)
        power_fit = power_law_fit(elog, fnonthermal, offset[run], extent[run])
        es, ee = power_fit.es, power_fit.ee
        fpower = power_fit.fpower
        powerIndex = "{%0.2f}" % power_fit.params[0]
        pname = r'$\sim \varepsilon^{' + powerIndex + '}$'
        es -= e_extend
        ee += e_extend
        p23, = ax.loglog(
            elog_norm[es:ee],
            fpower[es:ee] * 2,
            color=color,
            linestyle='--',
            linewidth=2,
            label=pname)
        colors_plot.append(color)
        # # Help for fitting
        # p12, = ax.loglog(elog_norm, fthermal, color=color)
        # p21, = ax.loglog(elog_norm[es], fnonthermal[es], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p22, = ax.loglog(elog_norm[ee], fnonthermal[ee], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p23, = ax.loglog(elog_norm, fpower)
        ax.set_xlim([1E-1, 3E2])
        ax.set_ylim([1E-5, 4E4])
        # shift *= 5
        run += 1

    ax.set_xlabel(
        r'$\varepsilon/\varepsilon_\text{th}$', fontdict=font, fontsize=24)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font, fontsize=24)
    ax.tick_params(labelsize=20)
    leg = ax.legend(
        loc=3,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    for color, text in zip(colors_plot, leg.get_texts()):
        text.set_color(color)
    ax.text(
        0.05,
        0.65,
        'R5',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.74,
        'R3',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.83,
        'R2',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.91,
        'R4',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)

    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    dir = '../img/spectra/'
    if not os.path.isdir(dir):
        os.makedirs(dir)
    fname = dir + 'spect_multi_electron_fitted.eps'
    fig.savefig(fname)

    plt.show()


def plot_spectra_beta_ion():
    """Plot spectra for multiple runs with different beta.

    """
    species = 'h'
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/spectra/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.15, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    base_dirs, run_names = ApJ_long_paper_runs()
    nruns = len(run_names)
    shift = 1
    offset = [50, 350, 40, 35]
    extent = [10, 30, 25, 70]
    shift = [1, 10, 500, 10000]
    run = 0
    e_extend = 40
    colors_plot = []
    e_nth = 50
    for run_name in run_names[:4]:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        ct = 1
        fname = dir + 'spectrum-' + species + '.1'
        file_exist = os.path.isfile(fname)
        while file_exist:
            ct += 1
            fname = dir + 'spectrum-' + species + '.' + str(ct)
            file_exist = os.path.isfile(fname)
        fname = dir + 'spectrum-' + species + '.' + str(ct - 1)
        elin, flin, elog, flog = get_energy_distribution(fname, n0)
        elog_norm = get_normalized_energy(species, elog, pic_info)
        flog *= shift[run]
        fthermal = fit_thermal_core(elog, flog)
        fnonthermal = flog - fthermal
        p1, = ax.loglog(elog_norm, flog, linewidth=2)
        color = p1.get_color()
        if run > 0:
            p11, = ax.loglog(
                elog_norm[e_nth:], fnonthermal[e_nth:], color=color)

        if run < 1:
            power_fit = power_law_fit(elog, flog, offset[run], extent[run])
        else:
            power_fit = power_law_fit(elog, fnonthermal, offset[run],
                                      extent[run])
        # power_fit = power_law_fit(elog, flog, 90, 30)
        # power_fit = power_law_fit(elog, fnonthermal, 35, 70)
        es, ee = power_fit.es, power_fit.ee
        fpower = power_fit.fpower
        es -= e_extend
        ee += e_extend
        powerIndex = "{%0.2f}" % power_fit.params[0]
        pname = r'$\sim \varepsilon^{' + powerIndex + '}$'
        if run > 0:
            p23, = ax.loglog(
                elog_norm[es:ee],
                fpower[es:ee] * 2,
                color=color,
                linestyle='--',
                linewidth=2,
                label=pname)
            colors_plot.append(color)
        # # Help for fitting
        # p21, = ax.loglog(elog_norm[es], flog[es], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p22, = ax.loglog(elog_norm[ee], flog[ee], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p21, = ax.loglog(elog_norm[es], fnonthermal[es], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p22, = ax.loglog(elog_norm[ee], fnonthermal[ee], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p23, = ax.loglog(elog_norm, fpower)
        ax.set_xlim([2E-1, 4E3])
        ax.set_ylim([1E-3, 5E7])
        # shift *= 5
        run += 1

    ax.set_xlabel(
        r'$\varepsilon/\varepsilon_\text{th}$', fontdict=font, fontsize=24)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font, fontsize=24)
    ax.tick_params(labelsize=20)
    leg = ax.legend(
        loc=3,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    for color, text in zip(colors_plot, leg.get_texts()):
        text.set_color(color)
    ax.text(
        0.45,
        0.05,
        'R8',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.59,
        0.05,
        'R7',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.78,
        0.05,
        'R1',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.92,
        0.05,
        'R6',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)

    ax.text(
        0.42,
        0.25,
        r'$\beta_e=0.2$',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes,
        rotation=-60)
    ax.text(
        0.55,
        0.25,
        r'$\beta_e=0.07$',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes,
        rotation=-60)
    ax.text(
        0.75,
        0.25,
        r'$\beta_e=0.02$',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes,
        rotation=-60)
    ax.text(
        0.85,
        0.33,
        r'$\beta_e=0.007$',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes,
        rotation=-60)

    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    dir = '../img/spectra/'
    if not os.path.isdir(dir):
        os.makedirs(dir)
    fname = dir + 'spect_beta_ion.eps'
    fig.savefig(fname)

    plt.show()


def plot_spectra_multi_ion():
    """Plot spectra for multiple runs with the same beta for electron.

    """
    species = 'h'
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/spectra/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.15, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    base_dirs, run_names = ApJ_long_paper_runs()
    nruns = len(run_names)
    shift = 1
    offset = [235, 220, 270, 310]
    extent = [80, 50, 50, 50]
    shift = [1, 10, 500, 10000]
    run = 0
    e_extend = 40
    colors_plot = []
    e_nth = [200, 150, 200, 250]
    ng = 3
    kernel = np.ones(ng) / float(ng)
    for run_name in run_names[4:8]:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        ct = 1
        fname = dir + 'spectrum-' + species + '.1'
        file_exist = os.path.isfile(fname)
        while file_exist:
            ct += 1
            fname = dir + 'spectrum-' + species + '.' + str(ct)
            file_exist = os.path.isfile(fname)
        fname = dir + 'spectrum-' + species + '.' + str(ct - 1)
        elin, flin, elog, flog = get_energy_distribution(fname, n0)
        elog_norm = get_normalized_energy(species, elog, pic_info)
        flog *= shift[run]
        flog = np.convolve(flog, kernel, 'same')
        fthermal = fit_thermal_core(elog, flog)
        fnonthermal = flog - fthermal
        p1, = ax.loglog(elog_norm, flog, linewidth=2)
        color = p1.get_color()
        p11, = ax.loglog(
            elog_norm[e_nth[run]:], fnonthermal[e_nth[run]:], color=color)
        # power_fit = power_law_fit(elog, fnonthermal, 310, 50)
        power_fit = power_law_fit(elog, fnonthermal, offset[run], extent[run])
        es, ee = power_fit.es, power_fit.ee
        fpower = power_fit.fpower
        powerIndex = "{%0.2f}" % power_fit.params[0]
        pname = r'$\sim \varepsilon^{' + powerIndex + '}$'
        es -= e_extend
        ee += e_extend
        p23, = ax.loglog(
            elog_norm[es:ee],
            fpower[es:ee] * 2,
            color=color,
            linestyle='--',
            linewidth=2,
            label=pname)
        colors_plot.append(color)
        # # Help for fitting
        # p12, = ax.loglog(elog_norm, fthermal, color=color)
        # p21, = ax.loglog(elog_norm[es], fnonthermal[es], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p22, = ax.loglog(elog_norm[ee], fnonthermal[ee], marker='.', markersize=10,
        #         linestyle='None', color=color)
        # p23, = ax.loglog(elog_norm, fpower)
        ax.set_xlim([1E-1, 2E3])
        ax.set_ylim([1E-3, 5E7])
        # shift *= 5
        run += 1

    ax.set_xlabel(
        r'$\varepsilon/\varepsilon_\text{th}$', fontdict=font, fontsize=24)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font, fontsize=24)
    ax.tick_params(labelsize=20)
    leg = ax.legend(
        loc=3,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    for color, text in zip(colors_plot, leg.get_texts()):
        text.set_color(color)
    ax.text(
        0.05,
        0.58,
        'R5',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.7,
        'R3',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.83,
        'R2',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.91,
        'R4',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)

    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    dir = '../img/spectra/'
    if not os.path.isdir(dir):
        os.makedirs(dir)
    fname = dir + 'spect_multi_ion.eps'
    fig.savefig(fname)

    plt.show()


def plot_guide_electron():
    """Plot spectra for multiple runs with guide field.

    """
    species = 'e'
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/spectra/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.15, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    base_dirs, run_names = guide_field_runs()
    nruns = len(run_names)
    shift = 1
    offset = [50, 70, 70, 80, 40]
    extent = [100, 50, 40, 40, 40]
    run = 0
    e_extend = 20
    colors_plot = []
    e_nth = 200
    for run_name in run_names:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        ct = 1
        fname = dir + 'spectrum-' + species + '.1'
        file_exist = os.path.isfile(fname)
        while file_exist:
            ct += 1
            fname = dir + 'spectrum-' + species + '.' + str(ct)
            file_exist = os.path.isfile(fname)
        fname = dir + 'spectrum-' + species + '.' + str(ct - 1)
        elin, flin, elog, flog = get_energy_distribution(fname, n0)
        elog_norm = get_normalized_energy(species, elog, pic_info)
        flog *= shift
        fthermal = fit_thermal_core(elog, flog)
        fnonthermal = flog - fthermal
        p1, = ax.loglog(elog_norm, flog, linewidth=2)
        color = p1.get_color()
        if run == 4:
            p11, = ax.loglog(
                elog_norm[e_nth:], fnonthermal[e_nth:], color=color)

        if run < 4:
            power_fit = power_law_fit(elog, flog, offset[run], extent[run])
        else:
            power_fit = power_law_fit(elog, fnonthermal, offset[run],
                                      extent[run])
        es, ee = power_fit.es, power_fit.ee
        fpower = power_fit.fpower
        color = p1.get_color()
        es -= e_extend
        ee += e_extend
        powerIndex = "{%0.2f}" % power_fit.params[0]
        pname = r'$\sim \varepsilon^{' + powerIndex + '}$'
        p23, = ax.loglog(
            elog_norm[es:ee],
            fpower[es:ee] * 2,
            color=color,
            linestyle='--',
            linewidth=2,
            label=pname)
        colors_plot.append(color)
        # # Help for fitting
        # if run < 4:
        #     p21, = ax.loglog(elog_norm[es], flog[es], marker='.', markersize=10,
        #             linestyle='None', color=color)
        #     p22, = ax.loglog(elog_norm[ee], flog[ee], marker='.', markersize=10,
        #             linestyle='None', color=color)
        #     p23, = ax.loglog(elog_norm, fpower)
        # else:
        #     p21, = ax.loglog(elog_norm[es], fnonthermal[es], marker='.',
        #             markersize=10, linestyle='None', color=color)
        #     p22, = ax.loglog(elog_norm[ee], fnonthermal[ee], marker='.',
        #             markersize=10, linestyle='None', color=color)
        #     p23, = ax.loglog(elog_norm, fpower)
        ax.set_xlim([1E-1, 4E2])
        ax.set_ylim([1E-4, 1E6])
        shift *= 10
        run += 1

    ax.set_xlabel(
        r'$\varepsilon/\varepsilon_\text{th}$', fontdict=font, fontsize=24)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font, fontsize=24)
    ax.tick_params(labelsize=20)
    leg = ax.legend(
        loc=3,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    for color, text in zip(colors_plot, leg.get_texts()):
        text.set_color(color)
    ax.text(
        0.05,
        0.6,
        r'$B_g=0$',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.7,
        r'$B_g=0.2$',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.8,
        r'$B_g=0.5$',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.05,
        0.9,
        r'$B_g=1.0$',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.4,
        0.93,
        r'$B_g=4.0$',
        color=colors[4],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)

    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    dir = '../img/spectra/'
    if not os.path.isdir(dir):
        os.makedirs(dir)
    fname = dir + 'spect_guide_electron.eps'
    fig.savefig(fname, transparent=True)

    plt.show()


def plot_guide_ion():
    """Plot ion spectra for multiple runs with guide field.

    """
    species = 'h'
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/spectra/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.15, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    base_dirs, run_names = guide_field_runs()
    nruns = len(run_names)
    shift = 1
    offset = [40, 40, 40, 40, 70]
    extent = [25, 25, 25, 25, 35]
    run = 0
    e_extend = 20
    colors_plot = []
    e_nth = 80
    plots = []
    for run_name in run_names:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        ct = 1
        fname = dir + 'spectrum-' + species + '.1'
        file_exist = os.path.isfile(fname)
        while file_exist:
            ct += 1
            fname = dir + 'spectrum-' + species + '.' + str(ct)
            file_exist = os.path.isfile(fname)
        fname = dir + 'spectrum-' + species + '.' + str(ct - 1)
        elin, flin, elog, flog = get_energy_distribution(fname, n0)
        elog_norm = get_normalized_energy(species, elog, pic_info)
        flog *= shift
        fthermal = fit_thermal_core(elog, flog)
        fnonthermal = flog - fthermal
        p1, = ax.loglog(elog_norm, flog, linewidth=2)
        color = p1.get_color()
        p11, = ax.loglog(elog_norm[e_nth:], fnonthermal[e_nth:], color=color)

        power_fit = power_law_fit(elog, fnonthermal, offset[run], extent[run])
        es, ee = power_fit.es, power_fit.ee
        fpower = power_fit.fpower
        color = p1.get_color()
        es -= e_extend
        ee += e_extend
        powerIndex = "{%0.2f}" % power_fit.params[0]
        pname = r'$\sim \varepsilon^{' + powerIndex + '}$'
        p23, = ax.loglog(
            elog_norm[es:ee],
            fpower[es:ee] * 2,
            color=color,
            linestyle='--',
            linewidth=2,
            label=pname)
        plots.append(p23)
        colors_plot.append(color)
        # # Help for fitting
        # p21, = ax.loglog(elog_norm[es], fnonthermal[es], marker='.',
        #         markersize=10, linestyle='None', color=color)
        # p22, = ax.loglog(elog_norm[ee], fnonthermal[ee], marker='.',
        #         markersize=10, linestyle='None', color=color)
        # p23, = ax.loglog(elog_norm, fpower)
        ax.set_xlim([2E-1, 7E2])
        ax.set_ylim([1E-3, 1E8])
        shift *= 10
        run += 1

    ax.set_xlabel(
        r'$\varepsilon/\varepsilon_\text{th}$', fontdict=font, fontsize=24)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font, fontsize=24)
    ax.tick_params(labelsize=20)
    leg1 = ax.legend(
        handles=plots[0:3],
        loc=3,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    leg2 = ax.legend(
        handles=plots[3:],
        loc=1,
        prop={'size': 20},
        ncol=1,
        shadow=False,
        fancybox=False,
        frameon=False)
    ax.add_artist(leg1)
    for color, text in zip(colors[0:3], leg1.get_texts()):
        text.set_color(color)
    for color, text in zip(colors[3:], leg2.get_texts()):
        text.set_color(color)
    ax.text(
        0.02,
        0.59,
        r'$B_g=0$',
        color=colors[0],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.02,
        0.69,
        r'$B_g=0.2$',
        color=colors[1],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.02,
        0.78,
        r'$B_g=0.5$',
        color=colors[2],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.02,
        0.88,
        r'$B_g=1.0$',
        color=colors[3],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)
    ax.text(
        0.25,
        0.93,
        r'$B_g=4.0$',
        color=colors[4],
        fontsize=20,
        horizontalalignment='left',
        verticalalignment='center',
        transform=ax.transAxes)

    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    dir = '../img/spectra/'
    if not os.path.isdir(dir):
        os.makedirs(dir)
    fname = dir + 'spect_guide_ion.eps'
    fig.savefig(fname, transparent=True)

    plt.show()


def get_maximum_energy_multi(species):
    """Get the maximum energy for multiple runs.
    """
    base_dirs, run_names = ApJ_long_paper_runs()
    nruns = len(run_names)
    emax = np.zeros(nruns)
    run = 0
    for run_name in run_names:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        ntp = pic_info.ntp
        emax_time = maximum_energy_particle(species, pic_info, dir)
        emax[run] = np.max(emax_time)
        run += 1
    for i in range(nruns):
        print("%s %6.2f" % (run_names[i], emax[i]))


def plot_maximum_energy_multi():
    """Plot the evolution of the maximum energy for multiple runs
    """
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    img_dir = '../img/emax/'
    if not os.path.isdir(img_dir):
        os.makedirs(img_dir)
    base_dirs, run_names = ApJ_long_paper_runs()
    nruns = len(run_names)
    emax = np.zeros(nruns)
    run = 0
    for run_name in run_names:
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        plot_maximum_energy(pic_info, dir)
        fname = img_dir + 'emax_' + run_name + '.eps'
        plt.savefig(fname)
        plt.close()


def plot_spectrum_series(species, pic_info, fpath, **kwargs):
    """Plot a series of energy spectra for one run.

    Args:
        species: particle species. 'e' for electron, 'h' for ion.
        pic_info: namedtuple for the PIC simulation information.
        fpath: file path that has the particle spectra data.
    """
    ntp = pic_info.ntp
    # ntp = 138
    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.16, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.grid(True)
    kwargs_plot = {
        "fpath": fpath,
        "is_thermal": False,
        "is_power": False,
        "xlim": kwargs["xlim"],
        "ylim": kwargs["ylim"],
        "color": 'k'
    }
    for ct in range(1, ntp - 1):
        color = plt.cm.jet(ct / float(ntp), 1)
        kwargs_plot["color"] = color
        plot_spectrum(ct, species, ax, pic_info, **kwargs_plot)
    kwargs_plot["color"] = 'k'
    # plot_spectrum(1, species, ax, pic_info, **kwargs_plot)
    # kwargs_plot["is_thermal"] = True
    # kwargs_plot["color"] = 'b'
    # plot_spectrum(ntp-1, species, ax, pic_info, **kwargs_plot)

    # if (species == 'e'):
    #     vth = pic_info.vthe
    #     ptl_mass = 1.0
    # else:
    #     vth = pic_info.vthi
    #     ptl_mass = pic_info.mime
    # gama = 1.0 / math.sqrt(1.0 - 3*vth**2)
    # eth = gama - 1.0
    # fname = fpath + "spectrum-" + species + "." + str(1).zfill(len(str(1)))
    # nx = pic_info.nx
    # ny = pic_info.ny
    # nz = pic_info.nz
    # nppc = pic_info.nppc
    # fnorm = nx * ny * nz * nppc
    # ene_lin, flin, ene_log, flog = get_energy_distribution(fname, fnorm)
    # ene_log_norm = get_normalized_energy(species, ene_log, pic_info)
    # f_intial = fitting_funcs.func_maxwellian(ene_log, fnorm, 1.5/eth)
    # nacc_ene, eacc_ene = accumulated_particle_info(ene_log, f_intial)
    # p41, = ax.loglog(ene_log_norm, f_intial/nacc_ene[-1]/ptl_mass,
    #         linewidth=2, color='k', linestyle='--', label=r'Initial')

    # ax.set_xlabel(r'$\varepsilon/\varepsilon_{th}$', fontdict=font)
    ax.set_xlabel(r'$\gamma -1 $', fontdict=font)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font)
    ax.tick_params(labelsize=20)

    # ebbed maximum energy plot
    emax_time = maximum_energy_particle(species, pic_info, fpath)
    tparticles = pic_info.tparticles
    xs, ys = 0.26, 0.26
    w1, h1 = 0.3, 0.3
    ax1 = fig.add_axes([xs, ys, w1, h1])
    nt1, = emax_time.shape
    nt2, = tparticles.shape
    nt = min(nt1, nt2)
    tparticles /= 100
    ax1.plot(tparticles[:nt], emax_time[:nt], linewidth=2, color='k')
    ax1.set_xlabel(r'$t\Omega_{ci}/100$', fontdict=font, fontsize=16)
    ax1.set_ylabel(
        r'$\varepsilon_\text{max}/\varepsilon_{th}$',
        fontdict=font,
        fontsize=16)
    ax1.tick_params(labelsize=12)


def plot_spectra_time_multi(species):
    """Plot time evolution of the particle energy spectra

    Args:
        species: particle species. 'e' for electron, 'h' for ion.
    """
    base_dirs, run_names = ApJ_long_paper_runs()
    # base_dirs, run_names = guide_field_runs()
    if not os.path.isdir('../img/'):
        os.makedirs('../img/')
    fig_dir = '../img/spectra/'
    if not os.path.isdir(fig_dir):
        os.makedirs(fig_dir)
    nrun = len(run_names)
    xlims = np.zeros((nrun, 2))
    ylims = np.zeros((nrun, 2))
    if species == 'e':
        xlims[0, :] = [5E-2, 2E2]
        ylims[0, :] = [1E-5, 2E2]
        xlims[1, :] = [5E-2, 2E2]
        ylims[1, :] = [1E-5, 2E2]
        xlims[2, :] = [5E-2, 2E2]
        ylims[2, :] = [1E-5, 2E2]
        xlims[3, :] = [5E-2, 6E2]
        ylims[3, :] = [1E-5, 2E2]
        xlims[4, :] = [5E-2, 2E2]
        ylims[4, :] = [1E-5, 2E2]
        xlims[5, :] = [5E-2, 3E2]
        ylims[5, :] = [1E-5, 2E3]
        xlims[6, :] = [5E-2, 3E2]
        ylims[6, :] = [1E-5, 5E2]
        xlims[7, :] = [5E-2, 3E2]
        ylims[7, :] = [1E-5, 2E2]
        xlims[8, :] = [5E-2, 3E2]
        ylims[8, :] = [1E-5, 2E2]
        # xlims[0,:] = [5E-2, 2E2]
        # ylims[0,:] = [1E-5, 2E2]
        # xlims[1,:] = [5E-2, 2E2]
        # ylims[1,:] = [1E-5, 2E2]
        # xlims[2,:] = [5E-2, 2E2]
        # ylims[2,:] = [1E-5, 2E2]
        # xlims[3,:] = [5E-2, 2E2]
        # ylims[3,:] = [1E-5, 2E2]
        # xlims[4,:] = [5E-2, 2E2]
        # ylims[4,:] = [1E-5, 2E2]
    else:
        xlims[0, :] = [5E-2, 2E2]
        ylims[0, :] = [1E-5, 2E2]
        xlims[1, :] = [5E-2, 2E2]
        ylims[1, :] = [1E-5, 2E2]
        xlims[2, :] = [2E-1, 7E2]
        ylims[2, :] = [1E-5, 2E2]
        xlims[3, :] = [2E-1, 2E3]
        ylims[3, :] = [1E-5, 2E2]
        xlims[4, :] = [5E-2, 7E2]
        ylims[4, :] = [1E-5, 2E2]
        xlims[5, :] = [5E-2, 6E2]
        ylims[5, :] = [1E-5, 2E3]
        xlims[6, :] = [5E-2, 7E2]
        ylims[6, :] = [1E-5, 5E2]
        xlims[7, :] = [5E-2, 7E2]
        ylims[7, :] = [1E-5, 2E2]
        xlims[8, :] = [2E-1, 3E2]
        ylims[8, :] = [1E-5, 2E2]
        # xlims[0,:] = [2E-1, 7E2]
        # ylims[0,:] = [1E-5, 2E2]
        # xlims[1,:] = [2E-1, 5E2]
        # ylims[1,:] = [1E-5, 2E2]
        # xlims[2,:] = [2E-1, 5E2]
        # ylims[2,:] = [1E-5, 2E2]
        # xlims[3,:] = [2E-1, 3E2]
        # ylims[3,:] = [1E-5, 2E2]
        # xlims[4,:] = [2E-1, 2E2]
        # ylims[4,:] = [1E-5, 2E2]
    for i in range(1):
        run_name = run_names[i]
        picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
        pic_info = read_data_from_json(picinfo_fname)
        dir = '../data/spectra/' + run_name + '/'
        n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
        kwargs = {"xlim": xlims[i], "ylim": ylims[i]}
        plot_spectrum_series(species, pic_info, dir, **kwargs)
        fname = fig_dir + 'spect_time_' + run_name + '_' + species + '.eps'
        plt.savefig(fname)
        plt.show()
        # plt.close()


def plot_final_energy_spectrum():
    """Plot final energy spectrum

    """
    species = 'e'
    run_name = 'mime25_beta0007'
    picinfo_fname = '../data/pic_info/pic_info_' + run_name + '.json'
    pic_info = read_data_from_json(picinfo_fname)
    fdir = '../data/spectra/' + run_name + '/'
    n0 = pic_info.nx * pic_info.ny * pic_info.nz * pic_info.nppc
    ct = 1
    fname = fdir + 'spectrum-' + species + '.1'
    file_exist = os.path.isfile(fname)
    while file_exist:
        ct += 1
        fname = fdir + 'spectrum-' + species + '.' + str(ct)
        file_exist = os.path.isfile(fname)

    fname = fdir + 'spectrum-' + species + '.' + str(ct - 1)
    elin, flin, elog, flog_e = get_energy_distribution(fname, n0)
    elog_norm_e = get_normalized_energy(species, elog, pic_info)
    nacc, eacc = accumulated_particle_info(elog_norm_e, flog_e)
    flog_e /= nacc[-1]

    fname = fdir + 'spectrum-h.' + str(ct - 1)
    elin, flin, elog, flog_i = get_energy_distribution(fname, n0)
    elog_norm_i = get_normalized_energy('i', elog, pic_info)
    nacc, eacc = accumulated_particle_info(elog_norm_i, flog_i)
    flog_i /= nacc[-1]

    if (species == 'e'):
        vth = pic_info.vthe
    else:
        vth = pic_info.vthi
    gama = 1.0 / math.sqrt(1.0 - 3 * vth**2)
    eth = gama - 1.0
    f_intial = fitting_funcs.func_maxwellian(elog, n0, 1.5 / eth)
    nacc, eacc = accumulated_particle_info(elog_norm_e, f_intial)
    f_intial /= nacc[-1]

    fig = plt.figure(figsize=[7, 5])
    xs, ys = 0.15, 0.15
    w1, h1 = 0.8, 0.8
    ax = fig.add_axes([xs, ys, w1, h1])
    ax.set_color_cycle(colors)
    ax.loglog(elog_norm_e, flog_e, linewidth=3, label='electron')
    ax.loglog(elog_norm_i, flog_i, linewidth=3, label='ion')
    ax.loglog(elog_norm_e, f_intial, linewidth=1, color='k', linestyle='--',
            label='initial')

    ax.set_xlim([5E-1, 7E3])
    ax.set_ylim([1E-8, 2E0])
    ax.set_xlabel(r'$\varepsilon/\varepsilon_\text{th}$', fontdict=font, fontsize=20)
    ax.set_ylabel(r'$f(\varepsilon)$', fontdict=font, fontsize=20)
    ax.tick_params(labelsize=16)

    colors_plot = [colors[0], colors[1], 'k']
    leg = ax.legend(loc=1, prop={'size': 20}, ncol=1,
            shadow=False, fancybox=False, frameon=False)
    for color, text in zip(colors_plot, leg.get_texts()):
        text.set_color(color)

    img_path = '../img/img_aiac/'
    mkdir_p(img_path)
    fname = img_path + 'final_spectra_' + run_name + '.eps'
    fig.savefig(fname)

    plt.show()


if __name__ == "__main__":
    # pic_info = pic_information.get_pic_info('../../')
    # ntp = pic_info.ntp
    # vthe = pic_info.vthe
    # kwargs = {"xlim":[2E-3, 5E0], "ylim":[1E-10,1E2]}
    # plot_spectrum_series('e', pic_info, '../spectrum/', **kwargs)
    # kwargs = {"xlim":[2E-4, 5E-1], "ylim":[1E-10,1E1]}
    # plot_spectrum_series('h', pic_info, '../spectrum/', **kwargs)
    # plt.savefig('../img/spectrum_fitting.eps')
    # plt.show()
    # plot_spectrum_bulk(ntp, 'e', pic_info)
    # plot_maximum_energy(ntp, pic_info)
    # move_energy_spectra()
    # calc_nonthermal_fraction('h')
    # plot_spectra_beta_electron()
    # plot_spectra_beta_electron_fitted()
    # plot_spectra_multi_electron()
    # plot_spectra_multi_electron_fitted()
    # plot_spectra_beta_ion()
    # plot_spectra_multi_ion()
    # plot_guide_electron()
    # plot_guide_ion()
    # get_maximum_energy_multi('h')
    # plot_maximum_energy_multi()
    # plot_spectra_time_multi('e')
    plot_final_energy_spectrum()
