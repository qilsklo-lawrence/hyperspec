clear; clc; close all;

[file, path] = uigetfile('*.mat','Select PL Project');

if isequal(file,0)
    error('No file selected.');
end

filename = fullfile(path,file);
loaded = load(filename);

if ~isfield(loaded,'share')
    error('Invalid project file.');
end

share = loaded.share;

if isfield(share,'fileType')
    validTypes = {'PLProject','ShareablePLProject_PublicFit'};
    if ~any(strcmpi(share.fileType, validTypes))
        error('Invalid project file.');
    end
else
    error('Invalid project file.');
end

if ~isfield(share,'fit_public')
    error('Invalid project file.');
end

X = share.X;
Y = share.Y;
uniqueX = share.uniqueX;
uniqueY = share.uniqueY;
index_map = share.index_map;

wl = share.wl;
raw = share.raw;

if isfield(share,'base')
    base = share.base;
else
    base = [];
end

if isfield(share,'corr')
    corr = share.corr;
else
    corr = [];
end

auc_map = share.auc_map;
sharpness_map = share.sharpness_map;
fit_results = share.fit_public;

if isfield(share,'si_peak_map')
    si_peak_map = share.si_peak_map;
else
    si_peak_map = nan(size(auc_map));
end

[Z_auc, ~] = buildMapMatrix(X, Y, auc_map, uniqueX, uniqueY);
[Z_sharp, ~] = buildMapMatrix(X, Y, sharpness_map, uniqueX, uniqueY);

fig = uifigure('Name','PL Mapping Viewer','Position',[60 60 1600 950]);
fig.KeyPressFcn = @onKeyPress;

mainGrid = uigridlayout(fig,[1 2]);
mainGrid.ColumnWidth = {'1.1x','1.4x'};
mainGrid.RowHeight = {'1x'};
mainGrid.Padding = [10 10 10 10];
mainGrid.ColumnSpacing = 12;

leftGrid = uigridlayout(mainGrid,[2 1]);
leftGrid.RowHeight = {'1x','1x'};
leftGrid.Padding = [0 0 0 0];
leftGrid.RowSpacing = 12;

aucPanel = uipanel(leftGrid,'Title','AUC Map');
aucGrid = uigridlayout(aucPanel,[2 1]);
aucGrid.RowHeight = {'1x',58};
aucGrid.Padding = [8 8 8 8];

ax_auc = uiaxes(aucGrid);
h_auc = imagesc(ax_auc, uniqueX, uniqueY, Z_auc);
set(ax_auc,'YDir','normal');
axis(ax_auc,'equal','tight');
colormap(ax_auc, redblue_cmap(256));
colorbar(ax_auc);
xlabel(ax_auc,'X (\mum)');
ylabel(ax_auc,'Y (\mum)');
set(ax_auc,'FontSize',14,'LineWidth',1.5);

hold(ax_auc,'on');
hMark_auc = plot(ax_auc,nan,nan,'ko','MarkerSize',12,'LineWidth',2);
hold(ax_auc,'off');

aucSliderGrid = uigridlayout(aucGrid,[2 2]);
aucSliderGrid.RowHeight = {24,24};
aucSliderGrid.ColumnWidth = {45,'1x'};
aucSliderGrid.Padding = [0 0 0 0];

uilabel(aucSliderGrid,'Text','Low');
s_auc_low = uislider(aucSliderGrid);
uilabel(aucSliderGrid,'Text','High');
s_auc_high = uislider(aucSliderGrid);

cleanSliderTicks(s_auc_low);
cleanSliderTicks(s_auc_high);
setupSliderLimits(ax_auc, Z_auc, s_auc_low, s_auc_high);

sharpPanel = uipanel(leftGrid,'Title','Sharpness Map');
sharpGrid = uigridlayout(sharpPanel,[2 1]);
sharpGrid.RowHeight = {'1x',86};
sharpGrid.Padding = [8 8 8 8];

ax_sharp = uiaxes(sharpGrid);
h_sharp = imagesc(ax_sharp, uniqueX, uniqueY, Z_sharp);
set(ax_sharp,'YDir','normal');
axis(ax_sharp,'equal','tight');
colormap(ax_sharp, redblue_cmap(256));
colorbar(ax_sharp);
xlabel(ax_sharp,'X (\mum)');
ylabel(ax_sharp,'Y (\mum)');
set(ax_sharp,'FontSize',14,'LineWidth',1.5);

hold(ax_sharp,'on');
hMark_sharp = plot(ax_sharp,nan,nan,'ko','MarkerSize',12,'LineWidth',2);
hold(ax_sharp,'off');

sharpSliderGrid = uigridlayout(sharpGrid,[3 2]);
sharpSliderGrid.RowHeight = {24,24,24};
sharpSliderGrid.ColumnWidth = {55,'1x'};
sharpSliderGrid.Padding = [0 0 0 0];

uilabel(sharpSliderGrid,'Text','Low');
s_sharp_low = uislider(sharpSliderGrid);
uilabel(sharpSliderGrid,'Text','High');
s_sharp_high = uislider(sharpSliderGrid);
uilabel(sharpSliderGrid,'Text','White');
s_sharp_white = uislider(sharpSliderGrid);

cleanSliderTicks(s_sharp_low);
cleanSliderTicks(s_sharp_high);
cleanSliderTicks(s_sharp_white);
setupSliderLimits(ax_sharp, Z_sharp, s_sharp_low, s_sharp_high);
setupWhiteSliderLimits(Z_sharp, s_sharp_white);

rightGrid = uigridlayout(mainGrid,[3 1]);
rightGrid.RowHeight = {'1x',75,40};
rightGrid.Padding = [0 0 0 0];
rightGrid.RowSpacing = 10;

specPanel = uipanel(rightGrid,'Title','Spectrum');
specGrid = uigridlayout(specPanel,[1 1]);
specGrid.Padding = [8 8 8 8];

ax_spec = uiaxes(specGrid);
title(ax_spec,'Click a pixel on either map, then use arrow keys');
xlabel(ax_spec,'Wavelength (nm)');
ylabel(ax_spec,'Intensity (a.u.)');
grid(ax_spec,'on');
set(ax_spec,'FontSize',14,'LineWidth',1.5);

axisPanel = uipanel(rightGrid,'Title','Spectrum Axis Controls');
axisGrid = uigridlayout(axisPanel,[1 10]);
axisGrid.ColumnWidth = {45,70,45,70,45,70,45,70,70,70};
axisGrid.RowHeight = {28};
axisGrid.Padding = [8 8 8 8];
axisGrid.ColumnSpacing = 6;

uilabel(axisGrid,'Text','X min');
editXmin = uieditfield(axisGrid,'numeric','Value',min(wl));

uilabel(axisGrid,'Text','X max');
editXmax = uieditfield(axisGrid,'numeric','Value',max(wl));

uilabel(axisGrid,'Text','Y min');
editYmin = uieditfield(axisGrid,'numeric','Value',0);

uilabel(axisGrid,'Text','Y max');
editYmax = uieditfield(axisGrid,'numeric','Value',1);

btnApplyAxis = uibutton(axisGrid,'Text','Apply');
btnAutoAxis = uibutton(axisGrid,'Text','Auto');

statusLabel = uilabel(rightGrid,'Text','Ready.');
statusLabel.FontSize = 13;

S.filename = filename;
S.X = X;
S.Y = Y;
S.uniqueX = uniqueX;
S.uniqueY = uniqueY;
S.index_map = index_map;

S.wl = wl;
S.raw = raw;
S.base = base;
S.corr = corr;

S.auc_map = auc_map;
S.sharpness_map = sharpness_map;
S.fit = fit_results;
S.si_peak_map = si_peak_map;

S.ax_auc = ax_auc;
S.ax_sharp = ax_sharp;
S.ax_spec = ax_spec;

S.h_auc = h_auc;
S.h_sharp = h_sharp;
S.hMark_auc = hMark_auc;
S.hMark_sharp = hMark_sharp;

S.s_auc_low = s_auc_low;
S.s_auc_high = s_auc_high;
S.s_sharp_low = s_sharp_low;
S.s_sharp_high = s_sharp_high;
S.s_sharp_white = s_sharp_white;

S.editXmin = editXmin;
S.editXmax = editXmax;
S.editYmin = editYmin;
S.editYmax = editYmax;
S.statusLabel = statusLabel;

S.currentXi = NaN;
S.currentYi = NaN;
S.currentIdx = NaN;

if isfield(share,'manualAxis')
    S.manualAxis = logical(share.manualAxis);
else
    S.manualAxis = false;
end

fig.UserData = S;

if isfield(share,'slider')
    if isfield(share.slider,'aucLowLimits') && isfield(share.slider,'aucLowValue')
        restoreSlider(s_auc_low, share.slider.aucLowLimits, share.slider.aucLowValue);
    end
    if isfield(share.slider,'aucHighLimits') && isfield(share.slider,'aucHighValue')
        restoreSlider(s_auc_high, share.slider.aucHighLimits, share.slider.aucHighValue);
    end
    if isfield(share.slider,'sharpLowLimits') && isfield(share.slider,'sharpLowValue')
        restoreSlider(s_sharp_low, share.slider.sharpLowLimits, share.slider.sharpLowValue);
    end
    if isfield(share.slider,'sharpHighLimits') && isfield(share.slider,'sharpHighValue')
        restoreSlider(s_sharp_high, share.slider.sharpHighLimits, share.slider.sharpHighValue);
    end
    if isfield(share.slider,'sharpWhiteLimits') && isfield(share.slider,'sharpWhiteValue')
        restoreSlider(s_sharp_white, share.slider.sharpWhiteLimits, share.slider.sharpWhiteValue);
    end
end

update_clim(ax_auc, s_auc_low, s_auc_high);
applySharpnessColormap(ax_sharp, s_sharp_low.Value, s_sharp_high.Value, s_sharp_white.Value);

if isfield(share,'specAxis')
    if isfield(share.specAxis,'xmin'), editXmin.Value = share.specAxis.xmin; end
    if isfield(share.specAxis,'xmax'), editXmax.Value = share.specAxis.xmax; end
    if isfield(share.specAxis,'ymin'), editYmin.Value = share.specAxis.ymin; end
    if isfield(share.specAxis,'ymax'), editYmax.Value = share.specAxis.ymax; end
end

S = fig.UserData;
S.editXmin = editXmin;
S.editXmax = editXmax;
S.editYmin = editYmin;
S.editYmax = editYmax;
fig.UserData = S;

h_auc.PickableParts = 'all';
h_auc.HitTest = 'on';
h_auc.ButtonDownFcn = @(src,event) updateSpectrumFromClick(src,event,fig);

h_sharp.PickableParts = 'all';
h_sharp.HitTest = 'on';
h_sharp.ButtonDownFcn = @(src,event) updateSpectrumFromClick(src,event,fig);

s_auc_low.ValueChangedFcn = @(src,event) update_clim(ax_auc,s_auc_low,s_auc_high);
s_auc_high.ValueChangedFcn = @(src,event) update_clim(ax_auc,s_auc_low,s_auc_high);

s_sharp_low.ValueChangedFcn = @(src,event) updateSharpnessColormap(fig);
s_sharp_high.ValueChangedFcn = @(src,event) updateSharpnessColormap(fig);
s_sharp_white.ValueChangedFcn = @(src,event) updateSharpnessColormap(fig);

btnApplyAxis.ButtonPushedFcn = @(src,event) applySpectrumAxis(fig);
btnAutoAxis.ButtonPushedFcn = @(src,event) autoSpectrumAxis(fig);

if isfield(share,'currentXi') && isfield(share,'currentYi') && ...
        ~isnan(share.currentXi) && ~isnan(share.currentYi) && ...
        share.currentXi >= 1 && share.currentXi <= numel(uniqueX) && ...
        share.currentYi >= 1 && share.currentYi <= numel(uniqueY)

    selectPixelByGrid(fig, share.currentXi, share.currentYi);

else
    [iy0, ix0] = find(~isnan(index_map), 1, 'first');
    if ~isempty(ix0)
        selectPixelByGrid(fig, ix0, iy0);
    end
end

function [Z, index_map] = buildMapMatrix(X, Y, values, uniqueX, uniqueY)

Z = nan(numel(uniqueY), numel(uniqueX));
index_map = nan(numel(uniqueY), numel(uniqueX));

for i = 1:numel(X)
    xi = find(uniqueX == X(i), 1);
    yi = find(uniqueY == Y(i), 1);

    if ~isempty(xi) && ~isempty(yi)
        Z(yi, xi) = values(i);
        index_map(yi, xi) = i;
    end
end

end

function updateSpectrumFromClick(src, event, fig)

S = fig.UserData;

x = event.IntersectionPoint(1);
y = event.IntersectionPoint(2);

[~, xi] = min(abs(S.uniqueX - x));
[~, yi] = min(abs(S.uniqueY - y));

idx = S.index_map(yi, xi);

if isnan(idx)
    [~, idx] = min(hypot(S.X - x, S.Y - y));
    xi = find(S.uniqueX == S.X(idx), 1);
    yi = find(S.uniqueY == S.Y(idx), 1);
end

selectPixelByGrid(fig, xi, yi);

end

function onKeyPress(fig, event)

S = fig.UserData;

if isnan(S.currentXi) || isnan(S.currentYi)
    [iy0, ix0] = find(~isnan(S.index_map), 1, 'first');
    if isempty(ix0), return; end
    S.currentXi = ix0;
    S.currentYi = iy0;
    fig.UserData = S;
end

xi = S.currentXi;
yi = S.currentYi;

switch event.Key
    case 'leftarrow'
        xi = xi - 1;
    case 'rightarrow'
        xi = xi + 1;
    case 'uparrow'
        yi = yi - 1;
    case 'downarrow'
        yi = yi + 1;
    otherwise
        return
end

xi = max(1, min(numel(S.uniqueX), xi));
yi = max(1, min(numel(S.uniqueY), yi));

if ~isnan(S.index_map(yi,xi))
    selectPixelByGrid(fig, xi, yi);
end

end

function selectPixelByGrid(fig, xi, yi)

S = fig.UserData;

idx = S.index_map(yi, xi);
if isnan(idx), return; end

S.currentXi = xi;
S.currentYi = yi;
S.currentIdx = idx;
fig.UserData = S;

plotSpectrumAtIndex(fig, idx);

end

function plotSpectrumAtIndex(fig, idx)

S = fig.UserData;

ax = S.ax_spec;
wl = S.wl(:)';

cla(ax);

plot(ax, wl, S.raw(idx,:), 'k', 'LineWidth',1.2);
hold(ax,'on');

leg = {'Raw'};

if ~isempty(S.base)
    plot(ax, wl, S.base(idx,:), 'r--', 'LineWidth',1.2);
    leg{end+1} = 'Baseline';
end

if ~isempty(S.corr)
    plot(ax, wl, S.corr(idx,:), 'b', 'LineWidth',1.2);
    leg{end+1} = 'Corrected';
end

hasFit = idx <= numel(S.fit) && isfield(S.fit,'xfit') && ...
         ~isempty(S.fit(idx).xfit) && isfield(S.fit,'yfit') && ...
         ~isempty(S.fit(idx).yfit);

if hasFit
    fr = S.fit(idx);

    if isfield(fr,'y_main') && ~isempty(fr.y_main)
        plot(ax, fr.xfit, fr.y_main, 'm--', 'LineWidth',1.5);
        leg{end+1} = 'Main peak';
    end

    plot(ax, fr.xfit, fr.yfit, 'm', 'LineWidth',2.2);
    leg{end+1} = 'Fit curve';

    if isfield(fr,'x0_main') && isfinite(fr.x0_main)
        xline(ax, fr.x0_main, '--m', 'LineWidth',1.2);
    end
end

legend(ax, leg, 'Location','best');
xlabel(ax,'Wavelength (nm)');
ylabel(ax,'Intensity (a.u.)');
grid(ax,'on');
set(ax,'FontSize',14,'LineWidth',1.5);

if hasFit
    fr = S.fit(idx);

    x0 = NaN;
    fwhm = NaN;

    if isfield(fr,'x0_main'), x0 = fr.x0_main; end
    if isfield(fr,'fwhm_main'), fwhm = fr.fwhm_main; end

    sharpVal = NaN;
    if idx <= numel(S.sharpness_map)
        sharpVal = S.sharpness_map(idx);
    end

    title(ax, sprintf('X = %.3f, Y = %.3f | Peak = %.2f nm | FWHM = %.2f nm | Sharpness = %.3g', ...
        S.X(idx), S.Y(idx), x0, fwhm, sharpVal));
else
    title(ax, sprintf('X = %.3f, Y = %.3f', S.X(idx), S.Y(idx)));
end

if S.manualAxis
    applyManualAxisToSpectrum(S);
else
    xlim(ax,'auto');
    ylim(ax,'auto');

    xl = xlim(ax);
    yl = ylim(ax);

    S.editXmin.Value = xl(1);
    S.editXmax.Value = xl(2);
    S.editYmin.Value = yl(1);
    S.editYmax.Value = yl(2);
end

set(S.hMark_auc,'XData',S.X(idx),'YData',S.Y(idx));
set(S.hMark_sharp,'XData',S.X(idx),'YData',S.Y(idx));

S.statusLabel.Text = sprintf('Selected pixel: X = %.3f, Y = %.3f, index = %d', S.X(idx), S.Y(idx), idx);

fig.UserData = S;

hold(ax,'off');
drawnow;

end

function applySpectrumAxis(fig)

S = fig.UserData;

xmin = S.editXmin.Value;
xmax = S.editXmax.Value;
ymin = S.editYmin.Value;
ymax = S.editYmax.Value;

if ~(xmin < xmax)
    S.statusLabel.Text = 'Invalid X range.';
    fig.UserData = S;
    return
end

if ~(ymin < ymax)
    S.statusLabel.Text = 'Invalid Y range.';
    fig.UserData = S;
    return
end

S.manualAxis = true;
fig.UserData = S;

applyManualAxisToSpectrum(S);

S.statusLabel.Text = sprintf('Spectrum axis set: X %.2f–%.2f, Y %.2g–%.2g.', xmin, xmax, ymin, ymax);

end

function applyManualAxisToSpectrum(S)

xlim(S.ax_spec,[S.editXmin.Value S.editXmax.Value]);
ylim(S.ax_spec,[S.editYmin.Value S.editYmax.Value]);

end

function autoSpectrumAxis(fig)

S = fig.UserData;

xlim(S.ax_spec,'auto');
ylim(S.ax_spec,'auto');

S.manualAxis = false;

xl = xlim(S.ax_spec);
yl = ylim(S.ax_spec);

S.editXmin.Value = xl(1);
S.editXmax.Value = xl(2);
S.editYmin.Value = yl(1);
S.editYmax.Value = yl(2);

S.statusLabel.Text = 'Spectrum axis set to auto.';
fig.UserData = S;

end

function setupSliderLimits(ax, Z, s_low, s_high)

Zvalid = Z(~isnan(Z) & isfinite(Z));
if isempty(Zvalid)
    s_low.Limits = [0 1];
    s_high.Limits = [0 1];
    s_low.Value = 0;
    s_high.Value = 1;
    return
end

zmin = min(Zvalid);
zmax = max(Zvalid);

if zmin == zmax
    zmax = zmin + eps;
end

clow = prctile(Zvalid,1);
chigh = prctile(Zvalid,99);

s_low.Limits = [zmin zmax];
s_high.Limits = [zmin zmax];

s_low.Value = clow;
s_high.Value = chigh;

cleanSliderTicks(s_low);
cleanSliderTicks(s_high);

caxis(ax,[clow chigh]);

end

function restoreSlider(sliderHandle, limitsValue, valueValue)

try
    if numel(limitsValue) == 2 && limitsValue(1) < limitsValue(2)
        sliderHandle.Limits = limitsValue;
        valueValue = max(limitsValue(1), min(limitsValue(2), valueValue));
        sliderHandle.Value = valueValue;
        cleanSliderTicks(sliderHandle);
    end
catch
end

end

function cleanSliderTicks(sliderHandle)

try
    sliderHandle.MajorTicks = [];
    sliderHandle.MajorTickLabels = {};
    sliderHandle.MinorTicks = [];
catch
end

end

function update_clim(ax, s_low, s_high)

lo = s_low.Value;
hi = s_high.Value;

if lo >= hi
    hi = lo + eps;
end

caxis(ax,[lo hi]);

end

function setupWhiteSliderLimits(Z, s_white)

Zvalid = Z(~isnan(Z) & isfinite(Z));
if isempty(Zvalid)
    s_white.Limits = [0 1];
    s_white.Value = 0.5;
    return
end

zmin = min(Zvalid);
zmax = max(Zvalid);

if zmin == zmax
    zmax = zmin + eps;
end

s_white.Limits = [zmin zmax];
s_white.Value = median(Zvalid);
cleanSliderTicks(s_white);

end

function updateSharpnessColormap(fig)

S = fig.UserData;

applySharpnessColormap(S.ax_sharp, ...
    S.s_sharp_low.Value, ...
    S.s_sharp_high.Value, ...
    S.s_sharp_white.Value);

end

function applySharpnessColormap(ax, lo, hi, whiteVal)

if lo >= hi
    hi = lo + eps;
end

whiteVal = max(lo + eps, min(hi - eps, whiteVal));

n = 256;
frac = (whiteVal - lo) / (hi - lo);

nBlue = max(2, round(frac * n));
nRed  = max(2, n - nBlue);

bluePart = [ ...
    linspace(0,1,nBlue)', ...
    linspace(0,1,nBlue)', ...
    ones(nBlue,1) ...
    ];

redPart = [ ...
    ones(nRed,1), ...
    linspace(1,0,nRed)', ...
    linspace(1,0,nRed)' ...
    ];

cmap = [bluePart; redPart];
colormap(ax, cmap);
caxis(ax,[lo hi]);

end

function cmap = redblue_cmap(n)

half = floor(n/2);

cmap = [ ...
    linspace(0,1,half)', linspace(0,1,half)', ones(half,1); ...
    ones(n-half,1), linspace(1,0,n-half)', linspace(1,0,n-half)' ...
    ];

end
