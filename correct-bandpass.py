from matplotlib import pyplot as plt
import numpy as np
import scipy.signal as sig
from astropy.io import fits
import os

"""
This script plots and corrects the Planck LFI bandpass profiles.
Required file is:
LFI_RIMO_R3.31.fits

Which can be downloaded here
https://pla.esac.esa.int/#docsw
"""
WIDTH = 3.54
hdus = fits.open('LFI_RIMO_R3.31.fits')
LABELDICT = {
    "30": ["27M", "27S", "28M", "28S",],
    "44": ["24M", "24S", "25M", "25S", "26M", "26S",],
    "70": [
        "18M",
        "18S",
        "19M",
        "19S",
        "20M",
        "20S",
        "21M",
        "21S",
        "22M",
        "22S",
        "23M",
        "23S",
    ],
}
def fmt(x, pos):
    """
    Text formatter
    """
    a, b = f"{x:.2e}".split("e")
    b = int(b)
    if float(a) == 1.00:
        return r"$10^{" + str(b) + "}$"
    elif float(a) == -1.00:
        return r"$-10^{" + str(b) + "}$"
    else:
        return fr"${a} \cdot 10^{b}$"

def find_nearest(array, value):
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return idx

def smooth_bandpass(bp,):
    """
    Smoothing function for bandpass profiles
    """
    b, a = sig.butter(3, 0.2)
    bp_corrected = sig.filtfilt(b, a, np.log(bp))
    return np.exp(bp_corrected)

def extrap1d(interpolator, label=None):
    xs = interpolator.x
    ys = interpolator.y
    idx = 2 if label in ["18M", "18S",] else 5  # Steeper slope on extrapolation

    def pointwise(x):
        if x < xs[0]:
            return ys[0] + (x - xs[0]) * (ys[10] - ys[0]) / (xs[5] - xs[0])
        elif x > xs[-1]:
            return ys[-1] + (x - xs[-1]) * (ys[-1] - ys[-10]) / (xs[-1] - xs[-idx])
        else:
            return interpolator(x)

    def ufunclike(xs):
        return np.array(list(map(pointwise, np.array(xs))))

    return ufunclike

def apply_corrections(bpx, bp, dataset, radiometer):
    """
    This function takes in a bandpass with a dataset label such as 30, 44 or 70
    and a radiometer label:
    """
    # Add 20% more profile to each end of the frequency array for future extrapolation
    dx = bpx[1] - bpx[0]
    bpx_full = np.concatenate(
        (
            np.arange(bpx[0], bpx[0] * 0.8, -dx)[1:][::-1],
            bpx,
            np.arange(bpx[-1], bpx[-1] * 1.2, dx)[1:],
        )
    )

    # Correction 1: Filter standing waves
    if dataset == "70":
        # Special case for 19M and 23M for well behaved smoothing.
        idx = 15 if radiometer in ["19M", "23M"] else 10
        bpx_corrected = bpx[:-idx]
        bp_corrected = smooth_bandpass(bp)[:-idx]
    else:
        bp_corrected = smooth_bandpass(bp)
        bpx_corrected = bpx

    # Correction 2: remove low-freq bump in 70
    if dataset == "70":
        idx = find_nearest(bpx, 61.5)
        bp_corrected = bp_corrected[idx:]
        bpx_corrected = bpx_corrected[idx:]
    if dataset == "44":
        # Also remove very low amplitude bump in 44 GHz
        idx = find_nearest(bpx, 38.0)
        bp_corrected = bp_corrected[idx:]
        bpx_corrected = bpx_corrected[idx:]

    # Correction 3: Add well defined cutoff to profiles by extrapolation
    if True:
        from scipy.interpolate import interp1d

        f = interp1d(bpx_corrected, np.log(bp_corrected))
        f = extrap1d(f, label=radiometer)
        bp_corrected = np.exp(f(bpx_full))

    # remove undefined areas
    bp_corrected[bp_corrected < 0.0] = 0.0  # Remove negative points if any

    return bpx_full, bp_corrected

def plotprofiles(dataset, min, max, savefig=False, fn="", outdir="nominal-bandpass/"):
    """
    Function for plotting profiles and their relative differences
    """
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    plt.rc("font", family="serif", size=8)
    plt.rcParams["mathtext.fontset"] = "stix"
    plt.rc(
        "text.latex", preamble=r"\usepackage{sfmath}",
    )
    from cycler import cycler
    plt.rcParams['axes.prop_cycle'] = cycler(color=plt.get_cmap('tab20').colors)
    f, (ax, ax2) = plt.subplots(
        2,
        1,
        sharex=False,
        figsize=(WIDTH,WIDTH*0.75),
        gridspec_kw={"height_ratios": [4, 1]},
        squeeze=True,
    )
    f.subplots_adjust(hspace=0.08)
    c = 0
    profs = []
    xprofs = []
    zorder = len(LABELDICT[dataset])
    for i, r in enumerate(LABELDICT[dataset]):
        hdu = hdus[hdus.index_of(f'BANDPASS_0{dataset}-{r}')]
        bp = hdu.data.field(1)
        bpx = hdu.data.field(0)
        profs.append(bp)
        xprofs.append(bpx)
        ax.semilogy(
            bpx,
            bp,
            label=r,
            linewidth=1,
            alpha=0.9,
            zorder=zorder,
        )
        zorder -= 1
    mean_line= ax.semilogy(
        xprofs[0],
        np.mean(profs, axis=0),
        color=f"black",
        linestyle="-",
        linewidth=1,
        zorder=100,
        alpha=0.9,
    )
    plt.yticks(rotation=90, va="center")
    aprofs = np.array(profs)
    mean = np.mean(profs, axis=0)  # aprofs.mean(axis=0)
    c = 0
    diffs = []
    diffs = aprofs - mean

    zorder = len(LABELDICT[dataset])
    for i, x in enumerate(diffs):
        ax2.plot(
            xprofs[i],
            x / np.max(diffs),
            color=f"C{c}",
            linewidth=1,
            alpha=0.8,
            zorder=zorder,
        )
        c += 1
        zorder -= 1

    ax.set_ylim(1e-4, 0.5)
    xpos=0.5175
    if dataset=="30":
        xpos=0.63
        ncol=2
    elif dataset=="44":
        ncol=3
    elif dataset=="70":
        ncol = 3
    
    # Make legend
    ax.legend(bbox_to_anchor=(xpos, 0.5),fontsize=7,ncol=ncol, frameon=False, handlelength=1.5)
    # Add separate mean legend
    ax3 = ax.twinx()
    ax3.get_yaxis().set_visible(False)
    ax3.spines["top"].set_visible(False)
    ax3.spines["bottom"].set_visible(False)
    ax3.spines["left"].set_visible(False)
    ax3.spines["right"].set_visible(False)
    ax3.legend(mean_line, [r"Mean"], bbox_to_anchor=(0.65, 0.59), fontsize=7, ncol=ncol, frameon=False, handlelength=1.5)

    # Adjust plot
    ax.set_xlim(min, max)
    ax2.set_xlim(min, max)# + (max - min) * shift)
    ax2.set_xlabel(r"Frequency, $\nu$ [GHz]")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    ax2.set_ylim(-1, 1)
    ax.set_ylabel(r"Normalized Bandpass")
    ax2.set_ylabel(r"$x-\bar{x}$")
    plt.draw()
    ax.set_xticklabels([])
    yticks = [1e-1, 1e-2, 1e-3]
    ax.set_yticks(yticks)
    ax.set_yticklabels(
        yticks, rotation=90, va="center",
    )
    ax.tick_params(axis="x", which="both", direction="in")
    ax2.tick_params(axis="x", which="both", direction="in")
    ax.tick_params(axis="y", which="both", direction="in")
    ax2.tick_params(axis="y", which="both", direction="in")

    ax.axhline(y=0, color="black", alpha=0.5, linestyle=":", linewidth=1)
    ax2.axhline(y=0, color="black", alpha=0.5, linestyle=":", linewidth=1)
    if savefig:
        plt.savefig(
            outdir + f"bpslog_{dataset}GHz{fn}.pdf",
            dpi=300,
            bbox_inches="tight",
            pad_inches=0.02,
        )
    else:
        plt.show()

def correct_and_plot(dataset, xmin=None, xmax=None, correct=True, plotfig=True, savefig=True, outdir="corrected-bandpass/"):
    """
    Function for correcting bandpass profiles.
    3x corrections
        1. Smooth
        2. Remove 70Ghz low frequency bump
        3. Add well defined cutoffs to ends of profiles
    """
    if not os.path.exists(outdir):
        os.makedirs(outdir)

    if plotfig: 
        plt.rc("font", family="serif", size=8)
        plt.rcParams["mathtext.fontset"] = "stix"
        plt.rc(
            "text.latex", preamble=r"\usepackage{sfmath}",
        )

        a = 0  # 1 # If add mean
        figsize = (WIDTH, int(len(LABELDICT[dataset]) / 2) * WIDTH*0.5)
        fig, ax = plt.subplots(
            int(len(LABELDICT[dataset]) / 2) + a,
            2,
            #subplot_kw=dict(box_aspect=1),
            sharex=True,
            sharey=True,
            figsize=figsize,
            gridspec_kw={"wspace": 0, "hspace": 0},
        )
        ax = ax.ravel()

    for i, r in enumerate(LABELDICT[dataset]):
        hdu = hdus[hdus.index_of(f'BANDPASS_0{dataset}-{r}')]
        bp = hdu.data.field(1)
        bpx = hdu.data.field(0)
        #bp = np.loadtxt(f"{path}bp_{r}.dat")
        #bpx = np.loadtxt(f"{path}bpx_{r}.dat")

        if correct:
            bpx_full, bp_corrected, = apply_corrections(bpx,bp,dataset=dataset,radiometer=r)
            np.savetxt(outdir+f"bp_corrected_{r}.dat", np.vstack((bpx_full, bp_corrected)).T)
        else:
            bpx_full, bp_corrected = np.loadtxt(outdir+f"bp_corrected_{r}.dat", unpack=True)

        if plotfig:
            ax[i].set_xlim(xmin, xmax)
            #ax[i].set_ylim(2e-6, 0.5)
            ax[i].set_ylim(2e-4, 0.5)
            ax[i].semilogy(
                bpx_full, bp_corrected, label="Corrected",linewidth=1
            )
            ax[i].tick_params(which="both", direction="in")
            ax[i].tick_params(axis="y", labelrotation=90)

            #ax[i].semilogy(bpx_hdf, bp_hdf, "+", label="Nominal_hdf", alpha=0.7)
            ax[i].semilogy(bpx, bp, label="Nominal", alpha=0.7, linewidth=1)
            ax[i].text(
                0.85,
                0.9,
                r,
                horizontalalignment="center",
                verticalalignment="center",
                transform=ax[i].transAxes,
            )
            ax[0].legend(
                frameon=False,
                fontsize=7,
                loc="upper center",
                bbox_to_anchor=(1.0, 1.15),
                ncol=2,
            )
            if i == 0:
                mean_bp = bp_corrected
            else:
                mean_bp += bp_corrected
        
        
        """
        if a == 1:
            # Mean BP per band
            ax[i + 1].semilogy(
                bpx_full, mean_bp / len(LABELDICT[dataset]), label=f"{dataset} mean corrected",
            )
            ax[i + 1].semilogy(bpx, bp, label=r, alpha=0.7)
            ax[i + 1].legend(frameon=False, fontsize=7)
        """

    # Save corrections
    if correct:
        np.savetxt(
            outdir + f"bp_corrected_{dataset}.dat",
            np.vstack((bpx_full, mean_bp / len(LABELDICT[dataset]))).T,
    )

    sax = fig.add_subplot(111, frameon=False)
    plt.tick_params(
        labelcolor="none",
        top=False,
        bottom=False,
        left=False,
        right=False,
        direction="in",
    )
    sax.set_xlabel(r"Frequency, $\nu$ [GHz]")
    sax.set_ylabel(rf"{dataset} GHz Normalized Bandpass")
    if savefig:
        plt.savefig(
            outdir + f"bpcorrected_{dataset}GHz.pdf",
            dpi=300,
            bbox_inches="tight",
            pad_inches=0.02,
        )
    else:
        plt.show()

if __name__ == "__main__":

    savefig=True
    plotprofiles("30", 23, 36.0,savefig=savefig,)
    plotprofiles("44", 38, 50.1,savefig=savefig,)
    plotprofiles("70", 57, 83,  savefig=savefig,)
    #plotprofiles("70", 77, 82.5,   savefig=savefig, fn="_zoom",)

    correct_and_plot("30", xmin=22, xmax=37, correct=False, plotfig=True, savefig=savefig)
    correct_and_plot("44", xmin=37, xmax=52, correct=False, plotfig=True, savefig=savefig)
    correct_and_plot("70", xmin=55, xmax=85, correct=False, plotfig=True, savefig=savefig)
