import 'package:flutter/material.dart';

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

  GlobalKey _ayahKey(int ayah) =>
      _ayahKeys.putIfAbsent(ayah, GlobalKey.new);

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
    final key = '${controller.currentSurah}:$id#$idx';
    if (key == _lastScrolledFocusKey) return;
    _lastScrolledFocusKey = key;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final stop = controller.stopById(id);
      if (stop == null) return;
      _ensureAyahFocused(stop.ayah, key);
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
        (hops == 0 && (targetAyah - mountedAyahs.last).abs() > 16 &&
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
              : ListView.builder(
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
                      ),
                    );
                  },
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
  });

  final List<Ayah> ayahs;
  final ReaderController controller;
  final GlobalKey Function(int ayah) ayahKeyFor;

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
  });

  final Ayah ayah;
  final ReaderController controller;

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
        _AyahMark(ayah: ayah, controller: controller),
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
  });

  final AyahWord word;
  final Ayah ayah;
  final ReaderController controller;
  final DemoSegmentRole role;

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
        wash = selected
            ? AppColors.wordGlow.withOpacity(0.55)
            : Colors.transparent;
        marker = Colors.transparent;
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 1),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        textDirection: TextDirection.rtl,
        children: [
          GestureDetector(
            behavior: HitTestBehavior.opaque,
            onLongPress: () => showAyahOptionsSheet(context, controller, ayah),
            child: DecoratedBox(
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
                child: Text(
                  word.text,
                  textDirection: TextDirection.rtl,
                  style: AppText.quran(
                    size: controller.quranSize,
                    color: AppColors.ink,
                    height: 1.35,
                  ),
                ),
              ),
            ),
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

    return StopBadge(
      key: ValueKey<String>('stop-${stop.id}-${activeScholar ?? "all"}'),
      symbol: stop.symbolForScholar(activeScholar),
      verdictLabel: stop.verdictLabelForScholar(activeScholar),
      isQila: stop.isQilaForScholar(activeScholar),
      selected: selected && !demoOn,
      compact: compact,
      hasDemoCue: hasDemos,
      semanticsLabel:
          'وقف ${stop.labelForScholar(activeScholar)} عند ${stop.word}',
      onTap: () {
        // Tap opens dock (default الأقوال when closed); same stop toggles close.
        controller.openStopDock(stop.id);
      },
      onLongPress: null,
    );
  }
}

class _AyahMark extends StatelessWidget {
  const _AyahMark({required this.ayah, required this.controller});

  final Ayah ayah;
  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: 'خيارات الآية ${arabicDigits(ayah.number)}',
      child: InkWell(
        onTap: () => showAyahOptionsSheet(context, controller, ayah),
        onLongPress: () => showAyahOptionsSheet(context, controller, ayah),
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
