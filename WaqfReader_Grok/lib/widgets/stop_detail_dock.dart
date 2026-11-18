import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
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

class _StopDetailDockState extends State<StopDetailDock>
    with SingleTickerProviderStateMixin {
  Offset? _origin;
  int? _pointer;
  bool _showSwipeHint = false;
  late final AnimationController _hintCtrl;
  late final Animation<double> _hintFade;
  late final Animation<Offset> _hintSlide;

  ReaderController get controller => widget.controller;

  @override
  void initState() {
    super.initState();
    _hintCtrl = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1400),
    );
    _hintFade = CurvedAnimation(
      parent: _hintCtrl,
      curve: const Interval(0.0, 0.2, curve: Curves.easeOut),
      reverseCurve: const Interval(0.0, 0.35, curve: Curves.easeIn),
    );
    _hintSlide = Tween<Offset>(
      begin: const Offset(0.18, 0),
      end: const Offset(-0.18, 0),
    ).animate(CurvedAnimation(parent: _hintCtrl, curve: Curves.easeInOut));

    WidgetsBinding.instance.addPostFrameCallback((_) => _maybePlayHint());
  }

  @override
  void didUpdateWidget(covariant StopDetailDock oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!oldWidget.controller.stopDockOpen && controller.stopDockOpen) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _maybePlayHint());
    }
  }

  void _maybePlayHint() {
    if (!mounted || !controller.stopDockOpen) return;
    if (!controller.consumeSwipeHint()) return;
    setState(() => _showSwipeHint = true);
    _hintCtrl.forward(from: 0).then((_) async {
      if (!mounted || !_showSwipeHint) return;
      await Future<void>.delayed(const Duration(milliseconds: 280));
      if (!mounted || !_showSwipeHint) return;
      await _hintCtrl.reverse();
      if (mounted) setState(() => _showSwipeHint = false);
    });
  }

  void _stopHintNow() {
    controller.dismissSwipeHint();
    if (!_showSwipeHint) return;
    _hintCtrl.stop();
    _hintCtrl.value = 0;
    setState(() => _showSwipeHint = false);
  }

  @override
  void dispose() {
    _hintCtrl.dispose();
    super.dispose();
  }

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

    const threshold = 48.0;
    if (dx.abs() < threshold) return;
    if (dx.abs() <= dy.abs()) return;

    _stopHintNow();

    final goNext = dx > 0;
    final moved = controller.stepDemoOrStop(goNext ? 1 : -1);
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
    final maxH = MediaQuery.sizeOf(context).height * 0.34;
    final hasDemos = stop.hasDemosAndMeanings;
    final tab = hasDemos ? controller.stopDockTab : 1;
    final dark = controller.panelDark;
    final bg = dark ? AppColors.sheet : AppColors.parchment;
    final muted = dark ? AppColors.sheetMuted : AppColors.muted;
    final accent = dark ? AppColors.goldSoft : AppColors.forest;
    final line = dark ? AppColors.sheetLine : AppColors.hairline;

    final visible = controller.visibleStops;
    final waqfIndex = visible.indexWhere((s) => s.id == stop.id);
    final waqfPos = waqfIndex >= 0 ? waqfIndex + 1 : 0;
    final waqfTotal = visible.length;

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
          child: Stack(
            children: [
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(8, 8, 4, 4),
                    child: Row(
                      children: [
                        Expanded(
                          child: _DockTab(
                            label: 'آراء العلماء',
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
                        if (waqfTotal > 0)
                          Padding(
                            padding: const EdgeInsetsDirectional.only(
                              start: 6,
                              end: 2,
                            ),
                            child: Text(
                              '${arabicDigits(waqfPos)} / ${arabicDigits(waqfTotal)}',
                              textAlign: TextAlign.center,
                              style: AppText.ui(
                                size: 12,
                                weight: FontWeight.w700,
                                color: muted,
                                height: 1.1,
                              ),
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
              if (_showSwipeHint)
                Positioned.fill(
                  child: IgnorePointer(
                    child: FadeTransition(
                      opacity: _hintFade,
                      child: ColoredBox(
                        color: bg.withOpacity(0.55),
                        child: Center(
                          child: SlideTransition(
                            position: _hintSlide,
                            child: Icon(
                              Icons.swipe,
                              size: 52,
                              color: accent.withOpacity(0.9),
                            ),
                          ),
                        ),
                      ),
                    ),
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
