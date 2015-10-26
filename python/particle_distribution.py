"""
Analysis procedures for particle energy spectrum.
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib.ticker import MaxNLocator
from matplotlib.colors import LogNorm
from matplotlib import rc
from mpl_toolkits.axes_grid1 import make_axes_locatable
import numpy as np
import scipy
from scipy import interpolate, signal
import math
import os.path
import struct
import collections
import pic_information
import color_maps as cm
import colormap.colormaps as cmaps
import subprocess
from spectrum_fitting import get_energy_distribution

rc('font', **{'family': 'serif', 'serif': ['Computer Modern']})
mpl.rc('text', usetex=True)
mpl.rcParams['text.latex.preamble'] = [r"\usepackage{amsmath}"]

font = {'family' : 'serif',
        #'color'  : 'darkred',
        'color'  : 'black',
        'weight' : 'normal',
        'size'   : 24,
        }

def read_boilerplate(fh):
    """Read boilerplate of a file

    Args:
        fh: file handler
    """
    offset = 0
    sizearr = np.memmap(fh, dtype='int8', mode='r', offset=offset,
            shape=(5), order='F')
    offset += 5
    cafevar = np.memmap(fh, dtype='int16', mode='r', offset=offset,
            shape=(1), order='F')
    offset += 2
    deadbeefvar = np.memmap(fh, dtype='int32', mode='r', offset=offset,
            shape=(1), order='F')
    offset += 4
    realone = np.memmap(fh, dtype='float32', mode='r', offset=offset,
            shape=(1), order='F')
    offset += 4
    doubleone = np.memmap(fh, dtype='float64', mode='r', offset=offset,
            shape=(1), order='F')


def read_particle_header(fh):
    """Read particle file header

    Args:
        fh: file handler.
    """
    offset = 23     # the size of the boilerplate is 23
    tmp1 = np.memmap(fh, dtype='int32', mode='r', offset=offset,
            shape=(6), order='F')
    offset += 6 * 4
    tmp2 = np.memmap(fh, dtype='float32', mode='r', offset=offset,
            shape=(10), order='F')
    offset += 10 * 4
    tmp3 = np.memmap(fh, dtype='int32', mode='r', offset=offset,
            shape=(4), order='F')
    v0header = collections.namedtuple("v0header", ["version", "type", "nt",
        "nx", "ny", "nz", "dt", "dx", "dy", "dz", "x0", "y0", "z0", "cvac",
        "eps0", "damp", "rank", "ndom", "spid", "spqm"])
    v0 = v0header(version=tmp1[0], type=tmp1[1], nt=tmp1[2], nx=tmp1[3],
            ny=tmp1[4], nz=tmp1[5], dt=tmp2[0], dx=tmp2[1], dy=tmp2[2],
            dz=tmp2[3], x0=tmp2[4], y0=tmp2[5], z0=tmp2[6], cvac=tmp2[7],
            eps0=tmp2[8], damp=tmp2[9], rank=tmp3[0], ndom=tmp3[1],
            spid=tmp3[2], spqm=tmp3[3])
    header_particle = collections.namedtuple("header_particle", ["size",
        "ndim", "dim"])
    offset += 4 * 4
    tmp4 = np.memmap(fh, dtype='int32', mode='r', offset=offset,
            shape=(3), order='F')
    pheader = header_particle(size=tmp4[0], ndim=tmp4[1], dim=tmp4[2])
    offset += 3 * 4
    return (v0, pheader, offset)


def read_particle_data(fname):
    """Read particle information from a file.

    Args:
        fname: file name.
    """
    fh = open(fname, 'r')
    read_boilerplate(fh)
    v0, pheader, offset = read_particle_header(fh)
    nptl = pheader.dim
    particle_type = np.dtype([('dxyz', np.float32, 3), ('icell', np.int32),
            ('u', np.float32, 3), ('q', np.float32)])
    fh.seek(offset, os.SEEK_SET)
    data = np.fromfile(fh, dtype=particle_type, count=nptl)
    fh.close()
    return (v0, pheader, data)


def calc_velocity_distribution(v0, pheader, ptl, pic_info, corners, nbins):
    """Calculate particle velocity distribution

    Args:
        v0: the header info for the grid.
        pheader: the header info for the particles.
        pic_info: namedtuple for the PIC simulation information.
        corners: the corners of the box in di.
        nbins: number of bins in each dimension.
    """
    dx = ptl['dxyz'][:, 0]
    dy = ptl['dxyz'][:, 1]
    dz = ptl['dxyz'][:, 2]
    icell = ptl['icell']
    ux = ptl['u'][:, 0]
    uy = ptl['u'][:, 1]
    uz = ptl['u'][:, 2]

    nx = v0.nx + 2
    ny = v0.ny + 2
    nz = v0.nz + 2
    iz = icell // (nx*ny)
    iy = (icell - iz*nx*ny) // nx
    ix = icell - iz*nx*ny - iy*nx

    z = v0.z0 + ((iz - 1.0) + (dz + 1.0) * 0.5) * v0.dz
    y = v0.y0 + ((iy - 1.0) + (dy + 1.0) * 0.5) * v0.dy
    x = v0.x0 + ((ix - 1.0) + (dx + 1.0) * 0.5) * v0.dx

    # di -> de
    smime = math.sqrt(pic_info.mime)
    x /= smime
    y /= smime
    z /= smime

    mask = ((x >= corners[0][0]) & (x <= corners[0][1]) &
            (y >= corners[1][0]) & (y <= corners[1][1]) &
            (z >= corners[2][0]) & (z <= corners[2][1]))
    ux_d = ux[mask]
    uy_d = uy[mask]
    uz_d = uz[mask]

    range = [[-1.0, 1.0], [-1.0, 1.0]]
    hist_xy, xedges, yedges = np.histogram2d(uy_d, ux_d, 
            bins=nbins, range=range)
    hist_xz, xedges, yedges = np.histogram2d(uz_d, ux_d, 
            bins=nbins, range=range)
    hist_yz, xedges, yedges = np.histogram2d(uz_d, uy_d, 
            bins=nbins, range=range)

    return (hist_xy, hist_xz, hist_yz, xedges, yedges)


def get_particle_distribution(base_directory, tindex, corners, mpi_ranks):
    """Read particle information.

    Args:
        base_directory: the base directory for the simulation data.
        tindex: the time index.
        corners: the corners of the box in di.
        mpi_ranks: PIC simulation MPI ranks for a selected region.
    """
    pic_info = pic_information.get_pic_info(base_directory)
    dir_name = base_directory + 'particle/T.' + str(tindex) + '/'
    fbase = dir_name + 'eparticle' + '.' + str(tindex) + '.'
    tx = pic_info.topology_x
    ty = pic_info.topology_y
    tz = pic_info.topology_z
    nbins = 64
    hist_xy = np.zeros((nbins, nbins))
    hist_xz = np.zeros((nbins, nbins))
    hist_yz = np.zeros((nbins, nbins))
    mpi_ranks = np.asarray(mpi_ranks)
    for ix in range(mpi_ranks[0, 0], mpi_ranks[0, 1]+1):
        for iy in range(mpi_ranks[1, 0], mpi_ranks[1, 1]+1):
            for iz in range(mpi_ranks[2, 0], mpi_ranks[2, 1]+1):
                mpi_rank = ix + iy*tx + iz*tx*ty
                fname = fbase + str(mpi_rank)
                (v0, pheader, data) = read_particle_data(fname)
                (vhist_xy, vhist_xz, vhist_yz, x, y) = \
                        calc_velocity_distribution(v0, pheader,
                        data, pic_info, corners, nbins)
                hist_xy += vhist_xy
                hist_xz += vhist_xz
                hist_yz += vhist_yz
    # uold = np.linspace(-1.0, 1.0, 64)
    # u1, u2 = np.meshgrid(uold, uold)
    # ng = 3
    # kernel = np.ones((ng,ng)) / float(ng*ng)
    # hist_xy = signal.convolve2d(hist_xy, kernel, 'same')
    # hist_xz = signal.convolve2d(hist_xz, kernel, 'same')
    # hist_yz = signal.convolve2d(hist_yz, kernel, 'same')
    # fxy = interpolate.interp2d(u1, u2, np.log10(hist_xy+0.5), kind='cubic')
    # fxz = interpolate.interp2d(u1, u2, np.log10(hist_xz+0.5), kind='cubic')
    # fyz = interpolate.interp2d(u1, u2, np.log10(hist_yz+0.5), kind='cubic')
    # unew = np.linspace(-1.0, 1.0, 200)
    # fxy_new = fxy(unew, unew)
    # fxz_new = fxz(unew, unew)
    # fyz_new = fyz(unew, unew)

    # fxy = fxy_new
    # fxz = fxz_new
    # fyz = fyz_new

    # vmax = np.max([np.max(hist_xy), np.max(hist_xz), np.max(hist_yz)])
    # vmax = math.log10(vmax)
    # xs, ys = 0.08, 0.17
    # w1, h1 = 0.24, 0.72
    # gap = 0.08
    # fig = plt.figure(figsize=(12, 4))
    # ax1 = fig.add_axes([xs, ys, w1, h1])
    # p1 = ax1.imshow(fxy_new, cmap=plt.cm.jet,
    #         extent=[np.min(x), np.max(x), np.min(y), np.max(y)],
    #         aspect='auto', origin='lower',
    #         vmin = 0.0, vmax = vmax)
    #         # interpolation='bicubic')
    # ax1.set_xlabel(r'$u_x$', fontdict=font, fontsize=20)
    # ax1.set_ylabel(r'$u_y$', fontdict=font, fontsize=20)
    # ax1.tick_params(labelsize=16)
    # xs += w1 + gap
    # ax2 = fig.add_axes([xs, ys, w1, h1])
    # p2 = ax2.imshow(fxz_new, cmap=plt.cm.jet,
    #         extent=[np.min(x), np.max(x), np.min(y), np.max(y)],
    #         aspect='auto', origin='lower',
    #         vmin = 0.0, vmax = vmax)
    # ax2.set_xlabel(r'$u_x$', fontdict=font, fontsize=20)
    # ax2.set_ylabel(r'$u_z$', fontdict=font, fontsize=20)
    # ax2.tick_params(labelsize=16)
    # xs += w1 + gap
    # ax3 = fig.add_axes([xs, ys, w1, h1])
    # p3 = ax3.imshow(fyz_new, cmap=plt.cm.jet,
    #         extent=[np.min(x), np.max(x), np.min(y), np.max(y)],
    #         aspect='auto', origin='lower',
    #         vmin = 0.0, vmax = vmax)
    #         # interpolation='bicubic')
    # ax3.set_xlabel(r'$u_y$', fontdict=font, fontsize=20)
    # ax3.set_ylabel(r'$u_z$', fontdict=font, fontsize=20)
    # ax3.tick_params(labelsize=16)
    # p1.set_cmap(plt.cm.get_cmap('hot'))
    # p2.set_cmap(plt.cm.get_cmap('hot'))
    # p3.set_cmap(plt.cm.get_cmap('hot'))
    # plt.show()


def set_mpi_ranks(pic_info, center=np.zeros(3), sizes=np.ones(3)*400):
    """Set MPI ranks for getting particle data

    Args:
        pic_info: namedtuple for the PIC simulation information.
        center: the center of a box in di.
        sizes: the sizes of the box in grids.
    Returns:
        corners: the corners of the box in di.
        mpi_ranks: MPI ranks in which the box is.
    """
    # The domain sizes for each MPI process (in di)
    dx_domain = pic_info.lx_di / pic_info.topology_x
    dy_domain = pic_info.ly_di / pic_info.topology_y
    dz_domain = pic_info.lz_di / pic_info.topology_z
    lx_di = pic_info.lx_di
    ly_di = pic_info.ly_di
    lz_di = pic_info.lz_di

    # The sizes of each cell
    dx_di = pic_info.dx_di
    dy_di = pic_info.dy_di
    dz_di = pic_info.dz_di
    hsize = sizes / 2.0
    xs = center[0] - hsize[0] * dx_di
    xe = center[0] + hsize[0] * dx_di
    ys = center[1] - hsize[1] * dy_di
    ye = center[1] + hsize[1] * dy_di
    zs = center[2] - hsize[2] * dz_di
    ze = center[2] + hsize[2] * dz_di

    # x in [0, lx_di], y in [-ly_di/2, ly_di/2], z in [-lz_di/2, lz_di/2]
    if (xs < 0): xs = 0.0
    if (xs > lx_di): xs = lx_di
    if (xe < 0): xe = 0.0
    if (xe > lx_di): xe = lx_di
    if (ys < -ly_di*0.5): ys = -ly_di*0.5
    if (ys > ly_di*0.5): ys = ly_di*0.5
    if (ye < -ly_di*0.5): ye = -ly_di*0.5
    if (ye > ly_di*0.5): ye = ly_di*0.5
    if (zs < -lz_di*0.5): zs = -lz_di*0.5
    if (zs > lz_di*0.5): zs = lz_di*0.5
    if (ze < -lz_di*0.5): ze = -lz_di*0.5
    if (ze > lz_di*0.5): ze = lz_di*0.5

    ixs = int(math.floor(xs / dx_domain))
    ixe = int(math.floor(xe / dx_domain))
    iys = int(math.floor((ys + ly_di*0.5) / dy_domain))
    iye = int(math.floor((ye + ly_di*0.5) / dy_domain))
    izs = int(math.floor((zs + lz_di*0.5) / dz_domain))
    ize = int(math.floor((ze + lz_di*0.5) / dz_domain))
    if (ixe >= pic_info.topology_x):
        ixe = pic_info.topology_x - 1
    if (iye >= pic_info.topology_y):
        iye = pic_info.topology_y - 1
    if (ize >= pic_info.topology_z):
        ize = pic_info.topology_z - 1

    corners = np.zeros((3, 2))
    mpi_ranks = np.zeros((3, 2))
    corners = [[xs, xe], [ys, ye], [zs, ze]]
    mpi_ranks = [[ixs, ixe], [iys, iye], [izs, ize]]
    return (corners, mpi_ranks)

def generate_spectrum_vdist_config(fname, **kwargs):
    """Generate spectrum and velocity distribution configuration

    Args:
        fname: filename of the configuration file.
    """
    with open(fname, 'w+') as f:
        center = kwargs['center']
        sizes = kwargs['sizes']
        f.write('***** Configuration file for velocity distribution *****\n')
        f.write('\n')
        f.write('nbins = 600\n')
        f.write('emax = 100.0\n')
        f.write('emin = 0.0001\n')
        f.write('xc/de = %6.2f\n' % center[0])
        f.write('yc/de = %6.2f\n' % center[1])
        f.write('zc/de = %6.2f\n' % center[2])
        f.write('xsize = %d\n' % sizes[0])
        f.write('ysize = %d\n' % sizes[1])
        f.write('zsize = %d\n' % sizes[2])
        f.write('nbins_vdist = %d\n' % kwargs['nbins'])
        f.write('vmax = %6.2f\n' % kwargs['vmax'])
        f.write('vmin = %6.2f\n' % kwargs['vmin'])
        f.write('tframe = %d\n' % kwargs['tframe'])
        f.close()


def get_spectrum_vdist(pic_info, dir='../',
        config_name='config_files/vdist_config.dat', **kwargs):
    """Get particle spectra and velocity distributions
    """
    fname = dir + config_name
    generate_spectrum_vdist_config(fname, **kwargs)
    cmd = './particle_spectrum_vdist_box ' + config_name
    p1 = subprocess.Popen([cmd], cwd='../', shell=True)
    # cmd = 'mpirun -np 16 ./particle_spectrum_vdist_box ' + config_name
    # p1 = subprocess.Popen([cmd], cwd='../', stdout=subprocess.PIPE, shell=True)
    p1.wait()


def read_velocity_distribution(species, tframe, pic_info,
        fpath='../vdistributions/'):
    """Read velocity distribution from a file.

    Args:
        fpath: file path for the data.
        species: particle species.
        tframe: time frame.
        pic_info: particle information namedtuple.
    """
    # 2D distributions
    if species == 'e':
        fname = fpath + 'vdist_2d-' + species + '.' + str(tframe)
    else:
        fname = fpath + 'vdist_2d-h.' + str(tframe)
    f = open(fname, 'r')
    center = np.zeros(3)
    sizes = np.zeros(3)
    offset = 0
    center = np.memmap(f, dtype='float32', mode='r', 
            offset=offset, shape=(3), order='C')
    offset = 3 * 4
    sizes = np.memmap(f, dtype='float32', mode='r', 
            offset=offset, shape=(3), order='C')
    offset += 3 * 4
    vmin, vmax = np.memmap(f, dtype='float32', mode='c', 
            offset=offset, shape=(2), order='C')
    offset += 2 * 4
    nbins, = np.memmap(f, dtype='int32', mode='r', 
            offset=offset, shape=1, order='C')
    offset += 4
    vbins_short = np.zeros(nbins)
    vbins_long = np.zeros(nbins*2)
    vbins_short = np.memmap(f, dtype='float64', mode='c', 
            offset=offset, shape=(nbins), order='C')
    offset += 8 * nbins
    vbins_long = np.memmap(f, dtype='float64', mode='c', 
            offset=offset, shape=(2*nbins), order='C')
    offset += 8 * nbins * 2
    fvel_para_perp = np.zeros((nbins, 2*nbins))
    fvel_xy = np.zeros((2*nbins, 2*nbins))
    fvel_xz = np.zeros((2*nbins, 2*nbins))
    fvel_yz = np.zeros((2*nbins, 2*nbins))
    fvel_para_perp = np.memmap(f, dtype='float64', mode='c', 
            offset=offset, shape=(nbins, 2*nbins), order='C')
    offset += 8 * nbins * 2 * nbins
    fvel_xy = np.memmap(f, dtype='float64', mode='c', 
            offset=offset, shape=(2*nbins, 2*nbins), order='C')
    offset += 8 * 2 * nbins * 2 * nbins
    fvel_xz = np.memmap(f, dtype='float64', mode='c', 
            offset=offset, shape=(2*nbins, 2*nbins), order='C')
    offset += 8 * 2 * nbins * 2 * nbins
    fvel_yz = np.memmap(f, dtype='float64', mode='c', 
            offset=offset, shape=(2*nbins, 2*nbins), order='C')
    f.close()

    if species == 'e':
        fname = fpath + 'vdist_1d-' + species + '.' + str(tframe)
    else:
        fname = fpath + 'vdist_1d-h.' + str(tframe)
    f = open(fname, 'r')
    # skip headers
    offset = 9 * 4 + 8 * nbins * 3
    fvel_para = np.zeros(2*nbins)
    fvel_perp = np.zeros(nbins)
    fvel_para = np.memmap(f, dtype='float64', mode='c', 
            offset=offset, shape=(2*nbins), order='C')
    offset += 8 * nbins * 2
    fvel_perp = np.memmap(f, dtype='float64', mode='c', 
            offset=offset, shape=(nbins), order='C')
    f.close()

    # Adjust the vbins. For ions, the actual saved variables is
    # sqrt(m_i) * u
    smime = math.sqrt(pic_info.mime)
    if species == 'h':
        vbins_short /= smime
        vbins_long /= smime
        vmin /= smime
        vmax /= smime

    # Add small number to the distributions to avoid zeros
    # delta = vmin_2d * 0.1
    delta = 0.01
    fvel_para_perp += delta
    fvel_xy += delta
    fvel_xz += delta
    fvel_yz += delta

    # delta = vmin_1d * 0.1
    fvel_para += delta
    fvel_perp += delta
    vmin_2d = min(np.min(fvel_para_perp[np.nonzero(fvel_para_perp)]),
            np.min(fvel_xy[np.nonzero(fvel_xy)]),
            np.min(fvel_xz[np.nonzero(fvel_xz)]),
            np.min(fvel_yz[np.nonzero(fvel_yz)]))
    vmax_2d = max(np.max(fvel_para_perp[np.nonzero(fvel_para_perp)]),
            np.max(fvel_xy[np.nonzero(fvel_xy)]),
            np.max(fvel_xz[np.nonzero(fvel_xz)]),
            np.max(fvel_yz[np.nonzero(fvel_yz)]))
    vmin_1d = min(np.min(fvel_para[np.nonzero(fvel_para)]),
            np.min(fvel_perp[np.nonzero(fvel_perp)]))
    vmax_1d = max(np.max(fvel_para[np.nonzero(fvel_para)]),
            np.max(fvel_perp[np.nonzero(fvel_perp)]))

    fvelocity = collections.namedtuple("fvelocity", 
            ['species', 'tframe', 'center', 'sizes', 'vmin', 'vmax', 'nbins',
             'vbins_short', 'vbins_long', 'fvel_para_perp', 'fvel_xy',
             'fvel_xz', 'fvel_yz', 'fvel_para', 'fvel_perp', 'vmin_2d',
             'vmax_2d', 'vmin_1d', 'vmax_1d'])

    fvel = fvelocity(species=species, tframe=tframe, center=center,
            sizes=sizes, vmin=vmin, vmax=vmax, nbins=nbins,
            vbins_short=vbins_short, vbins_long=vbins_long,
            fvel_para_perp=fvel_para_perp, fvel_xy=fvel_xy, fvel_xz=fvel_xz,
            fvel_yz=fvel_yz, fvel_para=fvel_para, fvel_perp=fvel_perp,
            vmin_2d=vmin_2d, vmax_2d=vmax_2d, vmin_1d=vmin_1d, vmax_1d=vmax_1d)
    return fvel


def read_energy_distribution(species, tframe, pic_info, fpath='../spectrum/'):
    """Read particle energy spectrum from a file.

    Args:
        fpath: file path for the data.
        species: particle species.
        tframe: time frame.
        pic_info: particle information namedtuple.
    """
    if species == 'e':
        fname = fpath + 'spectrum-' + species + '.' + str(tframe)
    else:
        fname = fpath + 'spectrum-h.' + str(tframe)
    ntot = pic_info.nx * pic_info.ny + pic_info.nz * pic_info.nppc
    elin, flin, elog, flog = get_energy_distribution(fname, ntot)
    fenergy = collections.namedtuple('fenergy',
            ['species', 'elin', 'flin', 'elog', 'flog'])
    fene = fenergy(species=species, elin=elin, flin=flin, elog=elog, flog=flog)
    return fene


if __name__ == "__main__":
    base_directory = '../../'
    pic_info = pic_information.get_pic_info(base_directory)
    ntp = pic_info.ntp
    vthe = pic_info.vthe
    particle_interval = pic_info.particle_interval
    pos = [pic_info.lx_di/10, 0.0, 2.0]
    corners, mpi_ranks = set_mpi_ranks(pic_info, pos)
    ct = 5 * particle_interval
    # get_particle_distribution(base_directory, ct, corners, mpi_ranks)
    smime = math.sqrt(pic_info.mime)
    lx_de = pic_info.lx_di * smime
    center = [0.5*lx_de, 0, 0]
    sizes = [50, 1, 8]
    kwargs = {'center':center, 'sizes':sizes, 'nbins':64, 'vmax':2.0,
            'vmin':0, 'tframe':10}
    get_spectrum_vdist(pic_info, **kwargs)
    # fpath = '../vdistributions/'
    # fvel = read_velocity_distribution(fpath, 'e', 10)
    # fpath = '../spectrum/'
    # fene = read_energy_distribution(fpath, 'e', 10, pic_info)
