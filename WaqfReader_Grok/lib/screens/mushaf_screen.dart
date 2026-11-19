import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../widgets/ayah_options_sheet.dart';
import '../widgets/ornament_divider.dart';
import '../widgets/stop_badge.dart';
import '../widgets/stop_detail_dock.dart';
import '../widgets/waqf_filter_bar.dart';

class MushafScreen extends StatefulWidget {
  const MushafScreen({super.key, required this.controller});

  final ReaderController controller;

  @override
  State<MushafScreen> createState() => _MushafScreenState();
}

class _MushafScreenState extends State<MushafScreen> {
  final Map<int, GlobalKey> _ayahKeys = <int, GlobalKey>{};
  final ScrollController _scrollController = ScrollController();
  String? _lastScrolledFocusKey;

  ReaderController get controller => widget.controller;

  GlobalKey _ayahKey(int ayah) => _ayahKeys.putIfAbsent(ayah, GlobalKey.new);

  @override
  void initState() {
    super.initState();
    controller.addListener(_onControllerChanged);
  }

  @override
  void didUpdateWidget(covariant MushafScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_onControllerChanged);
      widget.controller.addListener(_onControllerChanged);
    }
  }

  @override
  void dispose() {
    controller.removeListener(_onControllerChanged);
    _scrollController.dispose();
    super.dispose();
  }

  void _onControllerChanged() {
    final id = controller.selectedStopId;
    if (!controller.stopDockOpen || id == null) {
      _lastScrolledFocusKey = null;
      return;
    }
    final idx = controller.demoHighlightActive
        ? (controller.selectedDemoIndex ?? 0)
        : -1;
    final scholarKey = controller.demoHighlightActive
        ? (controller.selectedDemoScholar ?? '')
        : '';
    final key = '${controller.currentSurah}:$id#$scholarKey#$idx';
    if (key == _lastScrolledFocusKey) return;
    _lastScrolledFocusKey = key;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final stop = controller.stopById(id);
      if (stop == null) return;
      final demo = controller.demoHighlightActive
          ? controller.activeDemoHighlight
          : null;
      final focusAyah =
          demo == null ? stop.ayah : demo.ayahExtent(stop.ayah).$1;
      _ensureAyahFocused(focusAyah, key);
    });
  }

  void _ensureAyahFocused(
    int targetAyah,
    String expectedKey, {
    int hops = 0,
  }) {
    if (!mounted ||
        !controller.stopDockOpen ||
        _lastScrolledFocusKey != expectedKey) {
      return;
    }
    final ctx = _ayahKey(targetAyah).currentContext;
    if (ctx != null) {
      // Keep focused ayah in the upper part of the list, above the dock.
      Scrollable.ensureVisible(
        ctx,
        alignment: 0.08,
        duration: const Duration(milliseconds: 280),
        curve: Curves.easeOutCubic,
      );
      return;
    }
    if (hops >= 10 || !_scrollController.hasClients) return;

    final chunks = controller.currentAyahChunks;
    final targetChunk = chunks.indexWhere(
      (c) => c.any((a) => a.number == targetAyah),
    );
    if (targetChunk < 0 || chunks.isEmpty) return;

    final pos = _scrollController.position;
    final mountedAyahs = _ayahKeys.entries
        .where((e) => e.value.currentContext != null)
        .map((e) => e.key)
        .toList()
      ..sort();

    final double nextOffset;
    if (mountedAyahs.isEmpty ||
        (hops == 0 &&
            (targetAyah - mountedAyahs.last).abs() > 16 &&
            (targetAyah - mountedAyahs.first).abs() > 16)) {
      nextOffset = (pos.maxScrollExtent * (targetChunk / chunks.length))
          .clamp(pos.minScrollExtent, pos.maxScrollExtent);
    } else {
      final step = (pos.viewportDimension * 0.8 + 400).clamp(300.0, 900.0);
      nextOffset = (targetAyah > mountedAyahs.last
              ? pos.pixels + step
              : pos.pixels - step)
          .clamp(pos.minScrollExtent, pos.maxScrollExtent);
    }
    if ((nextOffset - pos.pixels).abs() < 1) return;
    _scrollController.jumpTo(nextOffset);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _ensureAyahFocused(targetAyah, expectedKey, hops: hops + 1);
    });
  }

  @override
  Widget build(BuildContext context) {
    final chunks = controller.currentAyahChunks;
    final dockOpen = controller.stopDockOpen;
    return Column(
      children: [
        WaqfFilterBar(controller: controller),
        const OrnamentDivider(),
        Expanded(
          child: chunks.isEmpty
              ? const _EmptyReading()
              : Listener(
                  key: const ValueKey<String>('mushaf-swipe-area'),
                  behavior: HitTestBehavior.translucent,
                  onPointerDown: _onPagePointerDown,
                  onPointerMove: _onPagePointerMove,
                  onPointerUp: _onPagePointerUp,
                  onPointerCancel: _onPagePointerCancel,
                  child: ListView.builder(
                    key: ValueKey<int>(controller.currentSurah),
                    controller: _scrollController,
                    padding: EdgeInsets.fromLTRB(12, 8, 12, dockOpen ? 24 : 12),
                    cacheExtent: 600,
                    itemCount: chunks.length,
                    itemBuilder: (context, index) {
                      final isLast = index == chunks.length - 1;
                      return Padding(
                        padding: EdgeInsets.only(bottom: isLast ? 0 : 14),
                        child: _ReadingChunk(
                          ayahs: chunks[index],
                          controller: controller,
                          ayahKeyFor: _ayahKey,
                          onOpenAyah: _openAyahOptions,
                        ),
                      );
                    },
                  ),
                ),
        ),
        if (dockOpen) StopDetailDock(controller: controller),
        if (!dockOpen)
          const Padding(
            padding: EdgeInsets.only(bottom: 4),
            child: OrnamentDivider(),
          ),
      ],
    );
  }

  // Horizontal swipe anywhere on the mushaf page cycles the open stop's
  // distinct-span demos (only when it has more than one). Listener does not
  // join the gesture arena, so vertical scrolling is unaffected.
  Offset? _pageOrigin;
  int? _pagePointer;
  bool _pageDraggedHorizontally = false;
  DateTime? _lastPageSwipeAt;

  bool get _suppressAyahOptions {
    if (_pageDraggedHorizontally) return true;
    final t = _lastPageSwipeAt;
    return t != null && DateTime.now().difference(t).inMilliseconds < 250;
  }

  void _openAyahOptions(Ayah ayah) {
    if (_suppressAyahOptions) return;
    showAyahOptionsSheet(context, controller, ayah);
  }

  void _onPagePointerDown(PointerDownEvent e) {
    _pageOrigin = e.position;
    _pagePointer = e.pointer;
    _pageDraggedHorizontally = false;
  }

  void _onPagePointerMove(PointerMoveEvent e) {
    if (_pagePointer != e.pointer || _pageOrigin == null) return;
    final dx = (e.position.dx - _pageOrigin!.dx).abs();
    final dy = (e.position.dy - _pageOrigin!.dy).abs();
    if (dx > 18 && dx > dy) {
      _pageDraggedHorizontally = true;
      _lastPageSwipeAt = DateTime.now();
    }
  }

  void _onPagePointerCancel(PointerCancelEvent e) {
    if (_pagePointer == e.pointer) {
      _pageOrigin = null;
      _pagePointer = null;
      _pageDraggedHorizontally = false;
    }
  }

  void _onPagePointerUp(PointerUpEvent e) {
    if (_pagePointer != e.pointer || _pageOrigin == null) return;
    final dx = e.position.dx - _pageOrigin!.dx;
    final dy = e.position.dy - _pageOrigin!.dy;
    final draggedHorizontally =
        _pageDraggedHorizontally || (dx.abs() >= 18 && dx.abs() > dy.abs());
    _pageOrigin = null;
    _pagePointer = null;
    _pageDraggedHorizontally = false;
    if (draggedHorizontally) {
      _lastPageSwipeAt = DateTime.now();
    }
    const threshold = 36.0;
    if (dx.abs() < threshold || dx.abs() <= dy.abs() * 1.2) return;
    final id = controller.selectedStopId;
    if (!controller.stopDockOpen || id == null) return;
    // Same direction convention as the dock: swipe right = next (RTL).
    if (controller.swipeStopVariant(id, dx > 0 ? 1 : -1)) {
      HapticFeedback.selectionClick();
    }
  }
}

class _EmptyReading extends StatelessWidget {
  const _EmptyReading();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(
          'لا نص للعرض في هذه السورة.',
          textAlign: TextAlign.center,
          style: AppText.ui(size: 16, color: AppColors.forestDeep),
        ),
      ),
    );
  }
}

class _ReadingChunk extends StatelessWidget {
  const _ReadingChunk({
    required this.ayahs,
    required this.controller,
    required this.ayahKeyFor,
    required this.onOpenAyah,
  });

  final List<Ayah> ayahs;
  final ReaderController controller;
  final GlobalKey Function(int ayah) ayahKeyFor;
  final void Function(Ayah ayah) onOpenAyah;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var a = 0; a < ayahs.length; a++) ...[
          if (a > 0) const SizedBox(height: 14),
          KeyedSubtree(
            key: ayahKeyFor(ayahs[a].number),
            child: _AyahBlock(
              ayah: ayahs[a],
              controller: controller,
              onOpenAyah: onOpenAyah,
            ),
          ),
        ],
      ],
    );
  }
}

class _AyahBlock extends StatelessWidget {
  const _AyahBlock({
    required this.ayah,
    required this.controller,
    required this.onOpenAyah,
  });

  final Ayah ayah;
  final ReaderController controller;
  final void Function(Ayah ayah) onOpenAyah;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      textDirection: TextDirection.rtl,
      alignment: WrapAlignment.center,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 0,
      runSpacing: 14,
      children: [
        ..._buildWordChildren(),
        _AyahMark(ayah: ayah, onOpenAyah: onOpenAyah),
      ],
    );
  }

  List<Widget> _buildWordChildren() {
    // One widget per word with fixed padding — demo wash must not regroup
    // tokens or change box sizes (that shifts word locations).
    return [
      for (final word in ayah.words)
        _WordToken(
          word: word,
          ayah: ayah,
          controller: controller,
          role: controller.demoRoleForWord(
            ayahNumber: ayah.number,
            wordIndex: word.index,
          ),
          ghost: controller.ghostDemoForWord(
            ayahNumber: ayah.number,
            wordIndex: word.index,
          ),
          qiraatOverride: controller.qiraatOverrideForWord(
            ayahNumber: ayah.number,
            wordIndex: word.index,
          ),
          onOpenAyah: onOpenAyah,
        ),
    ];
  }
}

class _WordToken extends StatelessWidget {
  const _WordToken({
    required this.word,
    required this.ayah,
    required this.controller,
    required this.role,
    required this.onOpenAyah,
    this.ghost,
    this.qiraatOverride,
  });

  final AyahWord word;
  final Ayah ayah;
  final ReaderController controller;
  final DemoSegmentRole role;
  final void Function(Ayah ayah) onOpenAyah;
  final ({StopDemoGroup group, DemoSegmentRole role})? ghost;
  final QiraatWordOverride? qiraatOverride;

  @override
  Widget build(BuildContext context) {
    final stopId = word.stopId;
    final stop = stopId == null ? null : controller.stopById(stopId);
    final visibleStop =
        (stop != null && controller.isStopVisible(stop)) ? stop : null;
    final selected = visibleStop != null &&
        controller.selectedStopId == visibleStop.id &&
        controller.stopDockOpen;
    final activeScholar = controller.selectedScholar;
    final qMod = qiraatOverride;
    final qColor = controller.qiraatHighlightColor;
    final qWash = controller.qiraatHighlightWash;

    final Color wash;
    final Color marker;
    switch (role) {
      case DemoSegmentRole.waqf:
        wash = AppColors.demoWaqfWash;
        marker = AppColors.demoWaqfMarker;
      case DemoSegmentRole.ibtida:
        wash = AppColors.demoIbtidaWash;
        marker = AppColors.demoIbtidaMarker;
      case DemoSegmentRole.none:
        // A swapped Qira'at word outside both segments still gets a faint
        // Qira'at wash; the segment colours stay reserved for waqf/ibtida.
        wash = qMod != null
            ? qWash
            : (selected
                ? AppColors.wordGlow.withOpacity(0.55)
                : Colors.transparent);
        marker = Colors.transparent;
    }

    final g = role == DemoSegmentRole.none ? ghost : null;
    final Color? ghostColor = g == null
        ? null
        : (g.role == DemoSegmentRole.waqf
                ? AppColors.demoWaqfMarker
                : AppColors.demoIbtidaMarker)
            .withOpacity(0.75);

    Widget box = DecoratedBox(
      decoration: BoxDecoration(
        color: wash,
        borderRadius: BorderRadius.circular(6),
        // Always reserve the same border width (transparent when idle).
        border: Border(
          bottom: BorderSide(
            color: marker,
            width: 2.4,
          ),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 1),
        child: qMod == null
            ? Text(
                word.text,
                textDirection: TextDirection.rtl,
                style: AppText.quran(
                  size: controller.quranSize,
                  color: AppColors.ink,
                  height: 1.35,
                ),
              )
            : QiraatWordText(
                word: qMod.modifiedWord,
                size: controller.quranSize,
                color: qColor,
              ),
      ),
    );
    if (qMod != null) {
      final painted = controller.qiraatDottedOutline
          ? CustomPaint(
              foregroundPainter: QiraatDottedOutlinePainter(color: qColor),
              child: box,
            )
          : box;
      box = Tooltip(
        message: 'قراءة أخرى: ${qMod.modifiedWord} (في حفص: ${qMod.hafsWord})',
        waitDuration: const Duration(milliseconds: 250),
        child: painted,
      );
    } else if (ghostColor != null) {
      box = Tooltip(
        message: 'اضغط لعرض: ${g!.group.scholars.join('، ')}',
        waitDuration: const Duration(milliseconds: 500),
        child: CustomPaint(
          foregroundPainter: _GhostUnderlinePainter(color: ghostColor),
          child: box,
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 1),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        textDirection: TextDirection.rtl,
        children: [
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTap: g == null
                ? null
                : () => controller.selectDemo(
                      scholar: g.group.scholar,
                      demoIndex: g.group.demoIndex,
                    ),
            onLongPress: () => onOpenAyah(ayah),
            child: box,
          ),
          if (visibleStop != null)
            _StopBadgeButton(
              stop: visibleStop,
              selected: selected,
              activeScholar: activeScholar,
              controller: controller,
              compact: true,
            ),
        ],
      ),
    );
  }
}

class _StopBadgeButton extends StatelessWidget {
  const _StopBadgeButton({
    required this.stop,
    required this.selected,
    required this.activeScholar,
    required this.controller,
    required this.compact,
  });

  final WaqfStop stop;
  final bool selected;
  final String? activeScholar;
  final ReaderController controller;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final hasDemos = stop.hasDemosAndMeanings;
    final demoOn = controller.demoHighlightActive &&
        controller.selectedStopId == stop.id &&
        controller.stopDockOpen;
    final groups =
        hasDemos ? controller.stopDemoGroupsFor(stop) : const <StopDemoGroup>[];
    final variantCount = groups.length;
    final activeVariant = (selected || demoOn) && variantCount > 1
        ? controller.activeStopDemoGroupIndex(stop)
        : -1;

    final badge = StopBadge(
      key: ValueKey<String>('stop-${stop.id}-${activeScholar ?? "all"}'),
      symbol: stop.symbolForScholar(activeScholar),
      verdictLabel: stop.verdictLabelForScholar(activeScholar),
      isQila: stop.isQilaForScholar(activeScholar),
      selected: selected && !demoOn,
      compact: compact,
      hasDemoCue: hasDemos && variantCount < 2,
      semanticsLabel:
          'وقف ${stop.labelForScholar(activeScholar)} عند ${stop.word}'
          '${variantCount > 1 ? '، ${arabicDigits(variantCount)} أوجه للتمثيل' : ''}',
      onTap: () {
        // Tap opens dock (default الأقوال when closed); same stop toggles close.
        controller.openStopDock(stop.id);
      },
      onLongPress: null,
    );
    if (variantCount < 2) return badge;

    // Multiple distinct demo spans: dots float above the symbol (no layout shift).
    // Swiping anywhere on the mushaf page cycles them (see _MushafScreenState).
    return Stack(
      key: ValueKey<String>('stop-variants-${stop.id}'),
      clipBehavior: Clip.none,
      alignment: Alignment.center,
      children: [
        badge,
        Positioned(
          top: -6,
          child: IgnorePointer(
            child: _VariantDots(
              count: variantCount,
              activeIndex: activeVariant,
            ),
          ),
        ),
      ],
    );
  }
}

class _VariantDots extends StatelessWidget {
  const _VariantDots({required this.count, required this.activeIndex});

  final int count;
  final int activeIndex;

  @override
  Widget build(BuildContext context) {
    final shown = count > 4 ? 4 : count;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1.5),
      decoration: BoxDecoration(
        color: AppColors.parchment,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(
          color: AppColors.gold.withOpacity(0.85),
          width: 0.8,
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.10),
            blurRadius: 2,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Row(
        key: const ValueKey<String>('variant-dots'),
        mainAxisSize: MainAxisSize.min,
        children: [
          for (var i = 0; i < shown; i++)
            AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              margin: const EdgeInsets.symmetric(horizontal: 1.2),
              width: i == activeIndex ? 10 : 5,
              height: 5,
              decoration: BoxDecoration(
                color: i == activeIndex
                    ? AppColors.forestDeep
                    : AppColors.gold.withOpacity(
                        activeIndex < 0 ? 0.85 : 0.45,
                      ),
                borderRadius: BorderRadius.circular(999),
              ),
            ),
        ],
      ),
    );
  }
}

class _AyahMark extends StatelessWidget {
  const _AyahMark({required this.ayah, required this.onOpenAyah});

  final Ayah ayah;
  final void Function(Ayah ayah) onOpenAyah;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'خيارات الآية ${arabicDigits(ayah.number)}',
      child: InkWell(
        onTap: () => onOpenAyah(ayah),
        onLongPress: () => onOpenAyah(ayah),
        borderRadius: BorderRadius.circular(11),
        child: Container(
          constraints: const BoxConstraints(minWidth: 28, minHeight: 22),
          margin: const EdgeInsets.symmetric(horizontal: 3),
          padding: const EdgeInsets.symmetric(horizontal: 5, vertical: 1),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(11),
            border: Border.all(color: AppColors.gold),
          ),
          child: Text(
            arabicDigits(ayah.number),
            style: AppText.ui(
              size: 10,
              weight: FontWeight.w700,
              color: AppColors.gold,
              height: 1.1,
            ),
          ),
        ),
      ),
    );
  }
}

/// Faint dotted underline marking an alternative demo span (tap to switch).
class _GhostUnderlinePainter extends CustomPainter {
  const _GhostUnderlinePainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1.8
      ..strokeCap = StrokeCap.round;
    final y = size.height - 1.2;
    const dash = 3.0;
    const gap = 3.0;
    var x = 2.0;
    while (x < size.width - 2) {
      final end = (x + dash).clamp(0.0, size.width - 2);
      canvas.drawLine(Offset(x, y), Offset(end, y), paint);
      x += dash + gap;
    }
  }

  @override
  bool shouldRepaint(covariant _GhostUnderlinePainter oldDelegate) =>
      oldDelegate.color != color;
}

/// Dotted rounded outline marking a non-Hafs Qira'at word swap without
/// colliding with the solid waqf/ibtida wash or shifting layout geometry.
class QiraatDottedOutlinePainter extends CustomPainter {
  const QiraatDottedOutlinePainter({required this.color});

  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final rect = Rect.fromLTWH(
      0.8,
      0.8,
      size.width - 1.6,
      size.height - 3.6,
    );
    if (rect.width <= 0 || rect.height <= 0) return;
    final path = Path()
      ..addRRect(RRect.fromRectAndRadius(rect, const Radius.circular(6)));
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4
      ..strokeCap = StrokeCap.round;
    const dash = 3.0;
    const gap = 2.6;
    for (final metric in path.computeMetrics()) {
      var dist = 0.0;
      while (dist < metric.length) {
        final end = (dist + dash).clamp(0.0, metric.length);
        canvas.drawPath(metric.extractPath(dist, end), paint);
        dist += dash + gap;
      }
    }
  }

  @override
  bool shouldRepaint(covariant QiraatDottedOutlinePainter oldDelegate) =>
      oldDelegate.color != color;
}

/// Renders [word] in the Mushaf's Amiri Quran (w400) face tinted in [color]
/// so both base letters and COLR harakat recolor uniformly without morphing.
class QiraatWordText extends StatelessWidget {
  const QiraatWordText({
    super.key,
    required this.word,
    required this.size,
    required this.color,
  });

  final String word;
  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return ColorFiltered(
      colorFilter: ColorFilter.mode(
        color,
        BlendMode.srcIn,
      ),
      child: Text(
        word,
        textDirection: TextDirection.rtl,
        style: AppText.quran(
          size: size,
          color: color,
          height: 1.35,
        ),
      ),
    );
  }
}
