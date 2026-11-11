import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../widgets/ayah_options_sheet.dart';
import '../widgets/demo_meanings_popup.dart';
import '../widgets/ornament_divider.dart';
import '../widgets/stop_badge.dart';
import '../widgets/waqf_bottom_sheet.dart';
import '../widgets/waqf_filter_bar.dart';

class MushafScreen extends StatefulWidget {
  const MushafScreen({super.key, required this.controller});

  final ReaderController controller;

  @override
  State<MushafScreen> createState() => _MushafScreenState();
}

class _MushafScreenState extends State<MushafScreen> {
  final GlobalKey _meaningsKey = GlobalKey();
  bool _wasDemoActive = false;

  ReaderController get controller => widget.controller;

  @override
  void initState() {
    super.initState();
    _wasDemoActive = controller.demoHighlightActive;
    controller.addListener(_onControllerChanged);
  }

  @override
  void didUpdateWidget(covariant MushafScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.controller != widget.controller) {
      oldWidget.controller.removeListener(_onControllerChanged);
      widget.controller.addListener(_onControllerChanged);
      _wasDemoActive = widget.controller.demoHighlightActive;
    }
  }

  @override
  void dispose() {
    controller.removeListener(_onControllerChanged);
    super.dispose();
  }

  void _onControllerChanged() {
    final active = controller.demoHighlightActive;
    if (active && !_wasDemoActive) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        final ctx = _meaningsKey.currentContext;
        if (ctx != null && mounted) {
          Scrollable.ensureVisible(
            ctx,
            alignment: 0.2,
            duration: const Duration(milliseconds: 320),
            curve: Curves.easeOutCubic,
          );
        }
      });
    }
    _wasDemoActive = active;
  }

  @override
  Widget build(BuildContext context) {
    final chunks = controller.currentAyahChunks;
    return Column(
      children: [
        WaqfFilterBar(controller: controller),
        const OrnamentDivider(),
        Expanded(
          child: chunks.isEmpty
              ? const _EmptyReading()
              : ListView.builder(
                  key: ValueKey<int>(controller.currentSurah),
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                  cacheExtent: 600,
                  itemCount: chunks.length,
                  itemBuilder: (context, index) {
                    final isLast = index == chunks.length - 1;
                    return Padding(
                      padding: EdgeInsets.only(bottom: isLast ? 0 : 14),
                      child: _ReadingChunk(
                        ayahs: chunks[index],
                        controller: controller,
                        meaningsKey: _meaningsKey,
                      ),
                    );
                  },
                ),
        ),
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
    required this.meaningsKey,
  });

  final List<Ayah> ayahs;
  final ReaderController controller;
  final GlobalKey meaningsKey;

  @override
  Widget build(BuildContext context) {
    final activeAyah = _activeDemoAyahNumber();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (var a = 0; a < ayahs.length; a++) ...[
          if (a > 0) const SizedBox(height: 14),
          _AyahBlock(
            ayah: ayahs[a],
            controller: controller,
            showMeaningsBox: activeAyah == ayahs[a].number,
            meaningsKey: meaningsKey,
          ),
        ],
      ],
    );
  }

  int? _activeDemoAyahNumber() {
    if (!controller.demoHighlightActive) return null;
    final id = controller.selectedStopId;
    if (id == null) return null;
    return controller.stopById(id)?.ayah;
  }
}

class _AyahBlock extends StatelessWidget {
  const _AyahBlock({
    required this.ayah,
    required this.controller,
    required this.showMeaningsBox,
    required this.meaningsKey,
  });

  final Ayah ayah;
  final ReaderController controller;
  final bool showMeaningsBox;
  final GlobalKey meaningsKey;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Wrap(
          textDirection: TextDirection.rtl,
          alignment: WrapAlignment.center,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 0,
          runSpacing: 14,
          children: [
            ..._buildWordChildren(),
            _AyahMark(ayah: ayah, controller: controller),
          ],
        ),
        if (showMeaningsBox)
          DemoMeaningsBox(
            key: meaningsKey,
            controller: controller,
          ),
      ],
    );
  }

  List<Widget> _buildWordChildren() {
    final roles = <DemoSegmentRole>[
      for (final word in ayah.words)
        controller.demoRoleForWord(
          ayahNumber: ayah.number,
          wordIndex: word.index,
        ),
    ];

    final out = <Widget>[];
    var i = 0;
    while (i < ayah.words.length) {
      final role = roles[i];
      if (role == DemoSegmentRole.none) {
        out.add(
          _PlainWordToken(
            word: ayah.words[i],
            ayah: ayah,
            controller: controller,
          ),
        );
        i += 1;
        continue;
      }

      final start = i;
      while (i < ayah.words.length && roles[i] == role) {
        i += 1;
      }
      out.add(
        _DemoRun(
          ayah: ayah,
          words: ayah.words.sublist(start, i),
          role: role,
          controller: controller,
        ),
      );
    }
    return out;
  }
}

class _PlainWordToken extends StatelessWidget {
  const _PlainWordToken({
    required this.word,
    required this.ayah,
    required this.controller,
  });

  final AyahWord word;
  final Ayah ayah;
  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final stopId = word.stopId;
    final stop = stopId == null ? null : controller.stopById(stopId);
    final visibleStop =
        (stop != null && controller.isStopVisible(stop)) ? stop : null;
    final selected =
        visibleStop != null && controller.selectedStopId == visibleStop.id;
    final activeScholar = controller.selectedScholar;

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
                color: selected
                    ? AppColors.wordGlow.withOpacity(0.55)
                    : Colors.transparent,
                borderRadius: BorderRadius.circular(6),
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
            _StopWithExplain(
              stop: visibleStop,
              selected: selected,
              activeScholar: activeScholar,
              controller: controller,
              compact: false,
            ),
        ],
      ),
    );
  }
}

/// Single smooth band wrapping several words (+ badges) for one demo role.
class _DemoRun extends StatelessWidget {
  const _DemoRun({
    required this.ayah,
    required this.words,
    required this.role,
    required this.controller,
  });

  final Ayah ayah;
  final List<AyahWord> words;
  final DemoSegmentRole role;
  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final wash = role == DemoSegmentRole.waqf
        ? AppColors.demoWaqfWash
        : AppColors.demoIbtidaWash;
    final marker = role == DemoSegmentRole.waqf
        ? AppColors.demoWaqfMarker
        : AppColors.demoIbtidaMarker;
    final activeScholar = controller.selectedScholar;

    final pieces = <Widget>[];
    for (final word in words) {
      final stopId = word.stopId;
      final stop = stopId == null ? null : controller.stopById(stopId);
      final visibleStop =
          (stop != null && controller.isStopVisible(stop)) ? stop : null;
      final selected =
          visibleStop != null && controller.selectedStopId == visibleStop.id;

      pieces.add(
        GestureDetector(
          behavior: HitTestBehavior.opaque,
          onLongPress: () => showAyahOptionsSheet(context, controller, ayah),
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
      );
      if (visibleStop != null) {
        pieces.add(
          _StopWithExplain(
            stop: visibleStop,
            selected: selected,
            activeScholar: activeScholar,
            controller: controller,
            compact: true,
          ),
        );
      }
    }

    return DecoratedBox(
      decoration: BoxDecoration(
        color: wash,
        borderRadius: BorderRadius.circular(8),
        border: Border(
          bottom: BorderSide(color: marker, width: 2.4),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(4, 3, 4, 4),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          textDirection: TextDirection.rtl,
          children: pieces,
        ),
      ),
    );
  }
}

class _StopWithExplain extends StatelessWidget {
  const _StopWithExplain({
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
        controller.selectedStopId == stop.id;

    final badge = StopBadge(
      key: ValueKey<String>('stop-${stop.id}-${activeScholar ?? "all"}'),
      symbol: stop.symbolForScholar(activeScholar),
      verdictLabel: stop.verdictLabelForScholar(activeScholar),
      isQila: stop.isQilaForScholar(activeScholar),
      selected: selected && !demoOn,
      compact: compact,
      semanticsLabel:
          'وقف ${stop.labelForScholar(activeScholar)} عند ${stop.word}',
      onTap: () {
        // Normal sheet: opinions only, no mushaf demo spans / ibtida cards.
        controller.select(stop.id);
        showWaqfSheet(
          context,
          controller,
          stop.id,
          includeDemos: false,
        );
      },
    );

    if (!hasDemos) return badge;

    return Padding(
      padding: const EdgeInsetsDirectional.only(start: 1, end: 1),
      child: Stack(
        clipBehavior: Clip.none,
        alignment: Alignment.center,
        children: [
          badge,
          Positioned(
            top: compact ? -2 : 0,
            left: compact ? -2 : 2,
            child: Tooltip(
              message: 'بيان الوقف والابتداء',
              child: Material(
                color: Colors.transparent,
                child: InkWell(
                  customBorder: const CircleBorder(),
                  onTap: () {
                    // Toggle: ؟ again clears highlight + dotted meanings box.
                    if (demoOn) {
                      controller.clearDemoHighlight();
                      return;
                    }
                    final op = demoOpinionForStop(stop, activeScholar);
                    controller.activateDemoHighlight(
                      stop.id,
                      scholar: op?.scholar,
                    );
                  },
                  child: Container(
                    width: 16,
                    height: 16,
                    alignment: Alignment.center,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: demoOn
                          ? AppColors.goldSoft
                          : AppColors.parchment,
                      border: Border.all(
                        color: demoOn ? AppColors.forest : AppColors.gold,
                        width: 1,
                      ),
                      boxShadow: const [
                        BoxShadow(
                          color: Color(0x22000000),
                          blurRadius: 2,
                          offset: Offset(0, 1),
                        ),
                      ],
                    ),
                    child: Text(
                      '؟',
                      style: AppText.ui(
                        size: 9,
                        weight: FontWeight.w800,
                        color: demoOn ? AppColors.forestDeep : AppColors.gold,
                        height: 1,
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
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
