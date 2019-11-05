"""
baesd on: http://www.apsipa.org/proceedings/2018/pdfs/0001945.pdf
"""
import numpy as np
from ..fbanks.mel_fbanks import mel_filter_banks
from ..utils.cepstral import cms, cmvn, lifter_ceps
from ..utils.spectral import rfft, dct, power_spectrum
from ..utils.exceptions import ParameterError, ErrorMsgs
from ..utils.preprocessing import pre_emphasis, framing, windowing, zero_handling


def psrcc(sig,
          fs=16000,
          num_ceps=13,
          pre_emph=0,
          pre_emph_coeff=0.97,
          win_len=0.025,
          win_hop=0.01,
          win_type="hamming",
          nfilts=26,
          nfft=512,
          low_freq=None,
          high_freq=None,
          scale="constant",
          gamma=-1/7,
          dct_type=2,
          use_energy=False,
          lifter=22,
          normalize=1):
    """
    Compute the Phase-based Spectral Root Cepstral Coefﬁcients (PSRCC) from an
    audio signal.

    Args:
        sig            (array) : a mono audio signal (Nx1) from which to compute features.
        fs               (int) : the sampling frequency of the signal we are working with.
                                 Default is 16000.
        num_ceps       (float) : number of cepstra to return.
                                 Default is 13.
        pre_emph         (int) : apply pre-emphasis if 1.
                                 Default is 1.
        pre_emph_coeff (float) : apply pre-emphasis filter [1 -pre_emph] (0 = none).
                                 Default is 0.97.
        win_len        (float) : window length in sec.
                                 Default is 0.025.
        win_hop        (float) : step between successive windows in sec.
                                 Default is 0.01.
        win_type       (float) : window type to apply for the windowing.
                                 Default is "hamming".
        nfilts           (int) : the number of filters in the filterbank.
                                 Default is 40.
        nfft             (int) : number of FFT points.
                                 Default is 512.
        low_freq         (int) : lowest band edge of mel filters (Hz).
                                 Default is 0.
        high_freq        (int) : highest band edge of mel filters (Hz).
                                 Default is samplerate / 2 = 8000.
        scale           (str)  : choose if max bins amplitudes ascend, descend or are constant (=1).
                                 Default is "constant".
        gamma          (float) : power coefficient for resulting energies
                                 Default -1/7.
        dct_type         (int) : type of DCT used - 1 or 2 (or 3 for HTK or 4 for feac).
                                 Default is 2.
        use_energy       (int) : overwrite C0 with true log energy
                                 Default is 0.
        lifter           (int) : apply liftering if value > 0.
                                 Default is 22.
        normalize        (int) : apply normalization if 1.
                                 Default is 0.

    Returns:
        (array) : 2d array of PSRCC features (num_frames x num_ceps)
    """
    # init freqs
    high_freq = high_freq or fs / 2
    low_freq = low_freq or 0

    # run checks
    if low_freq < 0:
        raise ParameterError(ErrorMsgs["low_freq"])
    if high_freq > (fs / 2):
        raise ParameterError(ErrorMsgs["high_freq"])
    if nfilts < num_ceps:
        raise ParameterError(ErrorMsgs["nfilts"])

    # pre-emphasis
    if pre_emph:
        sig = pre_emphasis(sig=sig, pre_emph_coeff=0.97)

    # -> framing
    frames, frame_length = framing(sig=sig,
                                   fs=fs,
                                   win_len=win_len,
                                   win_hop=win_hop)

    # -> windowing
    windows = windowing(frames=frames,
                        frame_len=frame_length,
                        win_type=win_type)

    # -> FFT -> unwarp: get phases -> convert phases to positive angles in deg
    fourrier_transform = rfft(x=windows, n=nfft)
    fft_phases = np.angle(z=fourrier_transform, deg=True)
    fft_phases = (360 + fft_phases) * (fft_phases <
                                       0) + fft_phases * (fft_phases > 0)

    # -> x Mel-fbanks
    mel_fbanks_mat = mel_filter_banks(nfilts=nfilts,
                                      nfft=nfft,
                                      fs=fs,
                                      low_freq=low_freq,
                                      high_freq=high_freq,
                                      scale=scale)
    features = np.dot(fft_phases, mel_fbanks_mat.T)

    # -> (.)^(gamma)
    features = features**gamma

    # assign 0 to values to be computed based on negative phases (otherwise results in nan)
    features[np.isnan(features)] = 0
    # assign max to values to be computed based on 0 phases (otherwise results in inf)
    features[np.isinf(features)] = features.max()

    # -> DCT(.)
    psrccs = dct(x=features, type=dct_type, axis=1, norm='ortho')[:, :num_ceps]

    # use energy for 1st features column
    if use_energy:
        # compute the power
        power_frames = power_spectrum(fourrier_transform)

        # compute total energy in each frame
        frame_energies = np.sum(power_frames, 1)

        # Handling zero enegies
        energy = zero_handling(frame_energies)
        psrccs[:, 0] = np.log(energy)

    # liftering
    if lifter > 0:
        psrccs = lifter_ceps(psrccs, lifter)

    # normalization
    if normalize:
        psrccs = cmvn(cms(psrccs))
    return psrccs