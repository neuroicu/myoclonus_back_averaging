# dependencies
import mne
import numpy as np
import matplotlib.pyplot as plt

"""import the EEG"""
# import EEG in .edf format
my_data='/path/XXX.edf'
raw = mne.io.read_raw_edf(my_data,preload=True)

# import provided sample EEG in .fif format (available on https://github.com/brohaut/myoclonus_back_averaging)
sample_data='/path/EEG_sample_B.fif'
raw=mne.io.read_raw_fif(sample_data,preload=True)

raw.set_channel_types({'CHIN1': 'emg','CHIN2': 'emg', 'ECGL': 'ecg','ECGR': 'ecg'})
print(raw.info) ; raw.info['ch_names']


""" jerk detection"""
no_filt=raw.copy() # keep raw signal to compare whith filtered signal later

# EMG filtering
picks = mne.pick_types(raw.info, eeg=False , emg=True, ecg=False) # select channel to filter
raw.notch_filter(60, picks=picks, filter_length='auto', phase='zero') # notch filter 60Hz
raw.filter(1, None, picks=picks, filter_length='auto', phase='zero') # high pass filter 1Hz

# compute the EMG trigger channel (CHIN1-CHIN2) and inject it in trig_chaN1
trig_chaN1 = mne.pick_channels(raw.info['ch_names'], include=['CHIN1'])
trig_chaN2 = mne.pick_channels(raw.info['ch_names'], include=['CHIN2'])
trig_chan = raw._data[trig_chaN1[0], :] - raw._data[trig_chaN2[0], :]
raw._data[trig_chaN1[0], :]=trig_chan

# compute derivative EMG trigger channel and inject it in trig_chaN2
trig_chan_deriv = np.gradient(trig_chan[:])
raw._data[trig_chaN2[0], :]=trig_chan_deriv

# high pass filter on the derivative to remove slow sloop
raw.filter(30, None, picks=trig_chaN2, filter_length='auto', phase='zero')

# plot raw EMG signal, filtered EMG, derivative and filtered derivative in the same graph
jitter=5e-4 # set distance between curves
plt.plot(raw._data[trig_chaN2[0],:]) # derivative HP 30Hz
plt.plot(trig_chan_deriv[:]-jitter) # derivative
plt.plot(raw._data[trig_chaN1[0],:]-2*jitter); # emg HP 1Hz + noch 60Hz
plt.plot(no_filt._data[trig_chaN1[0], :] - no_filt._data[trig_chaN2[0], :] -3*jitter); # raw EMG
plt.show()

# define the signal (best signal/noise ratio) to use for jerk detection (trig_chaN1 or trig_chaN2)
trig_chan=raw._data[trig_chaN2[0], :]# here we chose the filterd derivative signal

thresh= 8e-6 # define the detection threshold

set_offset= 0 # set an offset if needed (in secondes)
offset= int(round(raw.info['sfreq']*set_offset))
stim_length= round(raw.info['sfreq'] * (0.3)) # to avoid several triggers within 300ms)

triggers = np.zeros_like(trig_chan)
trigs = []
i=0; j=trig_chan.shape[0];
while i < j:
    if np.abs(trig_chan[i]) > np.abs(thresh):
        trigs.append(i)
        i += stim_length
    else:
        i += 1
trigs = np.array(trigs)
triggers[trigs.astype(int)-offset] = 1

triggers[55100:88100] = 0  # remove emg artefacts

trig_ch = mne.pick_channels(raw.info['ch_names'], include=['STI 014'])
raw._data[trig_ch, :]=triggers # replace STI 014 by triggers

# find events from triggers STI 014 channel
events = mne.find_events(raw)
event_id = {'Jerk': 1}; color = {1: 'green'}
# plot detected events
mne.viz.plot_events(events, raw.info['sfreq'], raw.first_samp, color=color,
                    event_id=event_id)

# filter the EEG (high pass 0.5 Hz + 60Hz notch)
picks=mne.pick_types(raw.info, eeg=True , emg=False, ecg=True)
raw.notch_filter(60, picks=picks, filter_length='auto', phase='zero')
raw.filter(0.5, None , picks=picks) #

montage = mne.channels.read_montage('standard_1020')
raw.set_montage(montage) # set 10-20 montage for topoplot
raw.set_eeg_reference(ref_channels=None) # set avergage reference

""" plot EEG + EMG and detected events for visual inspection"""
raw.plot(show_options=True, events=events, block = True, n_channels=9,
scalings=dict(eeg=7e-5, ecg=8e-4,emg=5e-5),start=0,duration=30,
color=dict(eeg='k', ecg='m', emg='b'))

# epoch from -300 to + 300ms according to jerk with a baseline correction applied from -300 to -200ms
tmin, tmax = -0.300, 0.300
epochs = mne.Epochs(raw, events=events, event_id=event_id,tmin=tmin,tmax=tmax, baseline=(-0.3, -0.2))
picks=mne.pick_types(epochs.info, eeg=True, emg=True, ecg=True)
evoked=epochs['Jerk'].average(picks=picks) # avergaging


"""plot the results"""
# plot EEG with EMG
picks=np.hstack((  mne.pick_types(epochs.info, eeg=True), trig_chaN1  ))
evoked.plot(spatial_colors=True, gfp=False, picks=picks, ylim = dict(eeg=[-50, 50],emg=[-80, 20]))
# plot EEG with topoplots
ts_args = dict(gfp=True); topomap_args = dict(sensors=False)
evoked.plot_joint(title='', times='peaks',ts_args=ts_args)
# plot specific topoplot
evoked.plot_topomap(times=[-0.02],sensors=False,vmin=-30,vmax=30)