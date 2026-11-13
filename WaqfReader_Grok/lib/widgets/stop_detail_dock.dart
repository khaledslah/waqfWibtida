import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/sample_data.dart';
import '../theme/app_theme.dart';
import 'demo_meanings_popup.dart';
import 'waqf_bottom_sheet.dart';

/// Fixed bottom host: demo box + original opinions sheet content.
/// Horizontal swipe anywhere on the sheet navigates waqfs (does not block scroll).
class StopDetailDock extends StatefulWidget {
  const StopDetailDock({super.key, required this.controller});

  final ReaderController controller;

  @override
  State<StopDetailDock> createState() => _StopDetailDockState();
}

class _StopDetailDockState extends State<StopDetailDock> {
  Offset? _origin;
  int? _pointer;

  ReaderController get controller => widget.controller;

  void _onPointerDown(PointerDownEvent e) {
    _origin = e.position;
    _pointer = e.pointer;
  }

  void _onPointerUp(PointerUpEvent e) {
    if (_pointer != e.pointer || _origin == null) return;
    final dx = e.position.dx - _origin!.dx;
    final dy = e.position.dy - _origin!.dy;
    _origin = null;
    _pointer = null;

    // Need a clear horizontal swipe; ignore mostly-vertical scrolls.
    const threshold = 48.0;
    if (dx.abs() < threshold) return;
    if (dx.abs() <= dy.abs()) return;

    // RTL: swipe left→right (dx > 0) = next waqf.
    final goNext = dx > 0;
    final moved = controller.stepVisibleStop(goNext ? 1 : -1);
    if (moved) {
      HapticFeedback.selectionClick();
    } else {
      HapticFeedback.lightImpact();
    }
  }

  void _onPointerCancel(PointerCancelEvent e) {
    if (_pointer == e.pointer) {
      _origin = null;
      _pointer = null;
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!controller.stopDockOpen) return const SizedBox.shrink();
    final stopId = controller.selectedStopId;
    final stop = stopId == null ? null : controller.stopById(stopId);
    if (stop == null) return const SizedBox.shrink();

    final bottom = MediaQuery.paddingOf(context).bottom;
    final maxH = MediaQuery.sizeOf(context).height * 0.48;
    final hasDemos = stop.hasDemosAndMeanings;
    final tab = hasDemos ? controller.stopDockTab : 1;
    final dark = controller.panelDark;
    final bg = dark ? AppColors.sheet : AppColors.parchment;
    final muted = dark ? AppColors.sheetMuted : AppColors.muted;
    final accent = dark ? AppColors.goldSoft : AppColors.forest;
    final line = dark ? AppColors.sheetLine : AppColors.hairline;

    // Listener sits above scrollables so swipe works anywhere without a tiny strip.
    return Material(
      color: bg,
      elevation: 6,
      child: Listener(
        behavior: HitTestBehavior.translucent,
        onPointerDown: _onPointerDown,
        onPointerUp: _onPointerUp,
        onPointerCancel: _onPointerCancel,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxHeight: maxH),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(12, 8, 4, 0),
                child: Row(
                  children: [
                    // RTL: first child sits on the right → الأقوال on the right.
                    Expanded(
                      child: _DockTab(
                        label: 'الأقوال',
                        selected: tab == 1,
                        enabled: true,
                        dark: dark,
                        onTap: () => controller.setStopDockTab(1),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: _DockTab(
                        label: 'المعاني',
                        selected: tab == 0,
                        enabled: hasDemos,
                        dark: dark,
                        onTap: hasDemos
                            ? () => controller.setStopDockTab(0)
                            : null,
                      ),
                    ),
                    IconButton(
                      tooltip: dark ? 'سمة فاتحة' : 'سمة داكنة',
                      onPressed: controller.togglePanelTheme,
                      icon: Icon(
                        dark
                            ? Icons.light_mode_outlined
                            : Icons.dark_mode_outlined,
                        color: accent,
                      ),
                    ),
                    IconButton(
                      tooltip: 'إغلاق',
                      onPressed: controller.closeStopDock,
                      icon: Icon(Icons.close, color: muted),
                    ),
                  ],
                ),
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Tooltip(
                  message: 'اسحب للتنقل بين الوقوف',
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(Icons.chevron_left, size: 16, color: muted),
                      Icon(Icons.swipe, size: 18, color: muted),
                      Icon(Icons.chevron_right, size: 16, color: muted),
                    ],
                  ),
                ),
              ),
              Divider(height: 1, thickness: 1, color: line),
              Flexible(
                child: tab == 0 && hasDemos
                    ? ListView(
                        padding: EdgeInsets.only(bottom: bottom + 4),
                        children: [
                          DemoMeaningsBox(
                            controller: controller,
                            showClose: false,
                            dark: dark,
                          ),
                        ],
                      )
                    : WaqfStopSheetPanel(
                        controller: controller,
                        stopId: stop.id,
                        includeDemos: false,
                        showAiSection: false,
                        dark: dark,
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _DockTab extends StatelessWidget {
  const _DockTab({
    required this.label,
    required this.selected,
    required this.enabled,
    required this.dark,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final bool enabled;
  final bool dark;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final accent = dark ? AppColors.goldSoft : AppColors.forest;
    final muted = dark ? AppColors.sheetMuted : AppColors.muted;
    final line = dark ? AppColors.sheetLine : AppColors.hairline;
    final color = !enabled
        ? muted.withOpacity(0.4)
        : (selected ? accent : muted);
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: enabled ? onTap : null,
        child: Opacity(
          opacity: enabled ? 1 : 0.45,
          child: Container(
            constraints: const BoxConstraints(minHeight: 40),
            alignment: Alignment.center,
            decoration: BoxDecoration(
              border: Border(
                bottom: BorderSide(
                  color: selected && enabled ? accent : line,
                  width: selected && enabled ? 2 : 1,
                ),
              ),
            ),
            child: Text(
              label,
              style: AppText.ui(
                size: 13,
                weight: selected && enabled ? FontWeight.w700 : FontWeight.w500,
                color: color,
                height: 1.1,
              ),
            ),
          ),
        ),
      ),
    );
  }
}
