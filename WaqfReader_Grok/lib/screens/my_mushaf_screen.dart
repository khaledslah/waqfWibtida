import 'dart:ui' show PointerDeviceKind;

import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../widgets/stop_badge.dart';
import '../widgets/waqf_bottom_sheet.dart';
import 'mushaf_screen.dart';

/// Standard 604-page Madinah Uthmani Mushaf view displaying only authentic
/// Uthmani pause marks plus stops explicitly added by the user from the
/// Waqf & Ibtida Mushaf ("أضف لمصحفي").
class MyMushafScreen extends StatefulWidget {
  const MyMushafScreen({super.key, required this.controller});

  final ReaderController controller;

  @override
  State<MyMushafScreen> createState() => _MyMushafScreenState();
}

class _MyMushafScreenState extends State<MyMushafScreen> {
  late final PageController _pageController;
  int _lastSyncedPage = 1;
  bool _syncingController = false;

  @override
  void initState() {
    super.initState();
    _lastSyncedPage = widget.controller.currentMushafPage.clamp(1, 604);
    _pageController = PageController(initialPage: _lastSyncedPage - 1);
    widget.controller.addListener(_onControllerChanged);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        widget.controller.openMushafPage(widget.controller.currentMushafPage);
      }
    });
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    _pageController.dispose();
    super.dispose();
  }

  void _onControllerChanged() {
    final targetPage = widget.controller.currentMushafPage.clamp(1, 604);
    if (targetPage == _lastSyncedPage) return;
    _lastSyncedPage = targetPage;
    if (!_pageController.hasClients) return;
    final currentIdx = (_pageController.page ?? (_lastSyncedPage - 1)).round();
    if (currentIdx == targetPage - 1) return;
    _syncingController = true;
    _pageController.jumpToPage(targetPage - 1);
    _syncingController = false;
  }

  void _goToPage(int page) {
    final p = page.clamp(1, 604);
    if (_pageController.hasClients) {
      _pageController.animateToPage(
        p - 1,
        duration: const Duration(milliseconds: 260),
        curve: Curves.easeOutCubic,
      );
    }
    widget.controller.openMushafPage(p);
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: widget.controller,
      builder: (context, _) {
        final controller = widget.controller;
        final currentPage = controller.currentMushafPage.clamp(1, 604);
        final pageInfo = controller.mushafPageInfo(currentPage);
        final savedStops = controller.sortedMyMushafStops;

        return Directionality(
          textDirection: TextDirection.rtl,
          child: ColoredBox(
            color: AppColors.parchment,
            child: Column(
              children: [
                _MyMushafToolbar(
                  controller: controller,
                  page: currentPage,
                  pageInfo: pageInfo,
                  savedCount: savedStops.length,
                  onPrevPage:
                      currentPage > 1 ? () => _goToPage(currentPage - 1) : null,
                  onNextPage:
                      currentPage < 604 ? () => _goToPage(currentPage + 1) : null,
                  onOpenPageJumper: () => _showPageJumperSheet(
                    context,
                    controller,
                    onSelectPage: _goToPage,
                  ),
                  onOpenSavedStops: () => _showSavedStopsSheet(
                    context,
                    controller,
                    onJumpToPage: _goToPage,
                  ),
                ),
                Expanded(
                  child: ScrollConfiguration(
                    behavior: ScrollConfiguration.of(context).copyWith(
                      dragDevices: const <PointerDeviceKind>{
                        PointerDeviceKind.touch,
                        PointerDeviceKind.mouse,
                        PointerDeviceKind.stylus,
                        PointerDeviceKind.invertedStylus,
                        PointerDeviceKind.trackpad,
                      },
                    ),
                    child: PageView.builder(
                      controller: _pageController,
                      itemCount: 604,
                      onPageChanged: (idx) {
                        final page = idx + 1;
                        _lastSyncedPage = page;
                        if (!_syncingController) {
                          controller.openMushafPage(page);
                        }
                      },
                      itemBuilder: (context, idx) {
                        final page = idx + 1;
                        return _UthmaniMushafPage(
                          key: ValueKey<int>(page),
                          controller: controller,
                          page: page,
                        );
                      },
                    ),
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _MyMushafToolbar extends StatelessWidget {
  const _MyMushafToolbar({
    required this.controller,
    required this.page,
    required this.pageInfo,
    required this.savedCount,
    required this.onPrevPage,
    required this.onNextPage,
    required this.onOpenPageJumper,
    required this.onOpenSavedStops,
  });

  final ReaderController controller;
  final int page;
  final MushafPageInfo? pageInfo;
  final int savedCount;
  final VoidCallback? onPrevPage;
  final VoidCallback? onNextPage;
  final VoidCallback onOpenPageJumper;
  final VoidCallback onOpenSavedStops;

  String _surahHeadline() {
    final ranges = pageInfo?.ranges;
    if (ranges == null || ranges.isEmpty) {
      return 'المصحف العثماني';
    }
    if (ranges.length == 1) {
      return controller.surahNameForNumber(ranges.first.surah);
    }
    final first = controller
        .surahNameForNumber(ranges.first.surah)
        .replaceFirst(RegExp(r'^سورة\s*'), '');
    final last = controller
        .surahNameForNumber(ranges.last.surah)
        .replaceFirst(RegExp(r'^سورة\s*'), '');
    return '$first – $last';
  }

  @override
  Widget build(BuildContext context) {
    final juz = pageInfo?.juz;
    return Container(
      decoration: const BoxDecoration(
        color: AppColors.parchment,
        border: Border(
          bottom: BorderSide(color: AppColors.hairline),
        ),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
      child: Row(
        children: [
          // Surah + Juz summary
          Expanded(
            child: InkWell(
              onTap: onOpenPageJumper,
              borderRadius: BorderRadius.circular(8),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _surahHeadline(),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: AppText.ui(
                        size: 13,
                        weight: FontWeight.w700,
                        color: AppColors.forestDeep,
                        height: 1.15,
                      ),
                    ),
                    if (juz != null)
                      Text(
                        'الجزء ${arabicDigits(juz)}',
                        style: AppText.ui(
                          size: 11,
                          color: AppColors.muted,
                          height: 1.15,
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ),

          // Next (right) / Page pill / Previous (left)
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              _NavArrowButton(
                key: const ValueKey('my-mushaf-next-btn'),
                tooltip: 'الصفحة التالية',
                icon: Icons.chevron_right_rounded,
                onPressed: onNextPage,
              ),
              InkWell(
                key: const ValueKey('my-mushaf-page-pill'),
                onTap: onOpenPageJumper,
                borderRadius: BorderRadius.circular(999),
                child: Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                  decoration: BoxDecoration(
                    color: AppColors.white,
                    borderRadius: BorderRadius.circular(999),
                    border: Border.all(color: AppColors.gold.withOpacity(0.55)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'ص ${arabicDigits(page)} / ٦٠٤',
                        style: AppText.ui(
                          size: 12,
                          weight: FontWeight.w700,
                          color: AppColors.ink,
                          height: 1.1,
                        ),
                      ),
                      const SizedBox(width: 2),
                      const Icon(
                        Icons.arrow_drop_down_rounded,
                        size: 16,
                        color: AppColors.muted,
                      ),
                    ],
                  ),
                ),
              ),
              _NavArrowButton(
                key: const ValueKey('my-mushaf-prev-btn'),
                tooltip: 'الصفحة السابقة',
                icon: Icons.chevron_left_rounded,
                onPressed: onPrevPage,
              ),
            ],
          ),

          const SizedBox(width: 6),

          // Saved custom stops pill
          InkWell(
            key: const ValueKey('my-mushaf-stops-pill'),
            onTap: onOpenSavedStops,
            borderRadius: BorderRadius.circular(999),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: savedCount > 0
                    ? AppColors.forestDeep
                    : AppColors.forestDeep.withOpacity(0.08),
                borderRadius: BorderRadius.circular(999),
                border: Border.all(
                  color: savedCount > 0
                      ? AppColors.goldSoft.withOpacity(0.75)
                      : AppColors.hairline,
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    savedCount > 0
                        ? Icons.bookmark_added
                        : Icons.bookmark_border_rounded,
                    size: 15,
                    color:
                        savedCount > 0 ? AppColors.goldSoft : AppColors.forestDeep,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    'وقوفي (${arabicDigits(savedCount)})',
                    style: AppText.ui(
                      size: 12,
                      weight: FontWeight.w700,
                      color: savedCount > 0
                          ? AppColors.white
                          : AppColors.forestDeep,
                      height: 1.1,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _NavArrowButton extends StatelessWidget {
  const _NavArrowButton({
    super.key,
    required this.tooltip,
    required this.icon,
    required this.onPressed,
  });

  final String tooltip;
  final IconData icon;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: tooltip,
      onPressed: onPressed,
      icon: Icon(
        icon,
        textDirection: TextDirection.ltr,
        size: 20,
        color: onPressed == null
            ? AppColors.muted.withOpacity(0.35)
            : AppColors.forestDeep,
      ),
      visualDensity: VisualDensity.compact,
      padding: EdgeInsets.zero,
      constraints: const BoxConstraints(minWidth: 30, minHeight: 30),
    );
  }
}

class _UthmaniMushafPage extends StatelessWidget {
  const _UthmaniMushafPage({
    super.key,
    required this.controller,
    required this.page,
  });

  final ReaderController controller;
  final int page;

  @override
  Widget build(BuildContext context) {
    final pageInfo = controller.mushafPageInfo(page);
    if (pageInfo == null) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: CircularProgressIndicator(),
        ),
      );
    }

    // Check that every surah rendered on this page is loaded in memory.
    final bundles = <int, AppFeedBundle>{};
    for (final range in pageInfo.ranges) {
      final b = controller.cachedBundleForSurah(range.surah);
      if (b == null) {
        return const Center(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: CircularProgressIndicator(),
          ),
        );
      }
      bundles[range.surah] = b;
    }

    // Build lookup by verse coordinate in addition to stopId.
    final savedByCoord = <String, MyMushafEntry>{};
    for (final entry in controller.sortedMyMushafStops) {
      savedByCoord['${entry.surah}:${entry.ayah}:${entry.wordIndex}'] = entry;
    }

    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 740),
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 24),
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(16, 18, 16, 18),
            decoration: BoxDecoration(
              color: AppColors.parchment,
              borderRadius: BorderRadius.circular(14),
              border: Border.all(
                color: AppColors.gold.withOpacity(0.55),
                width: 1.5,
              ),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withOpacity(0.05),
                  blurRadius: 10,
                  offset: const Offset(0, 3),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                for (var rIdx = 0; rIdx < pageInfo.ranges.length; rIdx++) ...[
                  if (rIdx > 0) const SizedBox(height: 16),
                  _RangeSection(
                    controller: controller,
                    range: pageInfo.ranges[rIdx],
                    bundle: bundles[pageInfo.ranges[rIdx].surah]!,
                    savedByCoord: savedByCoord,
                  ),
                ],
                const SizedBox(height: 16),
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 3,
                      ),
                      decoration: BoxDecoration(
                        color: AppColors.white,
                        borderRadius: BorderRadius.circular(999),
                        border: Border.all(
                          color: AppColors.gold.withOpacity(0.4),
                        ),
                      ),
                      child: Text(
                        arabicDigits(page),
                        style: AppText.ui(
                          size: 12,
                          weight: FontWeight.w700,
                          color: AppColors.muted,
                          height: 1.1,
                        ),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _SavedHighlightSpec {
  const _SavedHighlightSpec({
    required this.entry,
    required this.demo,
    required this.qiraatOverrides,
  });

  final MyMushafEntry entry;
  final WaqfDemoAndMeaning? demo;
  final List<QiraatWordOverride> qiraatOverrides;
}

class _RangeSection extends StatelessWidget {
  const _RangeSection({
    required this.controller,
    required this.range,
    required this.bundle,
    required this.savedByCoord,
  });

  final ReaderController controller;
  final MushafPageRange range;
  final AppFeedBundle bundle;
  final Map<String, MyMushafEntry> savedByCoord;

  @override
  Widget build(BuildContext context) {
    final ayahs = bundle.ayahs
        .where((a) => a.number >= range.startAyah && a.number <= range.endAyah)
        .toList();
    final startsAtBeginning = range.startAyah == 1;
    final showBismillah =
        startsAtBeginning && range.surah != 1 && range.surah != 9;

    final activeSpecs = <_SavedHighlightSpec>[];
    final specByStopId = <String, _SavedHighlightSpec>{};
    for (final entry in controller.sortedMyMushafStops) {
      if (entry.surah != range.surah) continue;
      final stop = bundle.stopsById[entry.stopId];
      final demo =
          stop == null ? null : controller.resolveMyMushafDemo(entry, stop);
      final (minAyah, maxAyah) =
          demo != null ? demo.ayahExtent(entry.ayah) : (entry.ayah, entry.ayah);
      if (maxAyah < range.startAyah || minAyah > range.endAyah) continue;
      final overrides = (stop != null && demo != null)
          ? controller.qiraatOverridesFor(stop, demo, ayahs: bundle.ayahs)
          : const <QiraatWordOverride>[];
      final spec = _SavedHighlightSpec(
        entry: entry,
        demo: demo,
        qiraatOverrides: overrides,
      );
      activeSpecs.add(spec);
      specByStopId[entry.stopId] = spec;
    }

    final tokens = <Widget>[];
    for (final ayah in ayahs) {
      for (final word in ayah.words) {
        final customEntry = (word.stopId != null
                ? controller.myMushafEntryFor(word.stopId)
                : null) ??
            savedByCoord['${range.surah}:${ayah.number}:${word.index}'];

        var role = DemoSegmentRole.none;
        MyMushafEntry? highlightOwner;
        if (customEntry != null) {
          final spec = specByStopId[customEntry.stopId];
          final ownRole = spec?.demo == null
              ? DemoSegmentRole.none
              : demoSegmentRoleForWord(
                  demo: spec!.demo,
                  wordIndex: word.index,
                  ayahNumber: ayah.number,
                  stopAyah: customEntry.ayah,
                );
          role = ownRole == DemoSegmentRole.none ? DemoSegmentRole.waqf : ownRole;
          highlightOwner = customEntry;
        } else {
          for (final spec in activeSpecs) {
            if (spec.demo != null) {
              final r = demoSegmentRoleForWord(
                demo: spec.demo,
                wordIndex: word.index,
                ayahNumber: ayah.number,
                stopAyah: spec.entry.ayah,
              );
              if (r != DemoSegmentRole.none) {
                role = r;
                highlightOwner = spec.entry;
                break;
              }
            } else if (spec.entry.ayah == ayah.number &&
                spec.entry.wordIndex == word.index) {
              role = DemoSegmentRole.waqf;
              highlightOwner = spec.entry;
              break;
            }
          }
        }

        QiraatWordOverride? qMod;
        for (final spec in activeSpecs) {
          for (final m in spec.qiraatOverrides) {
            if (m.ayahNumber == ayah.number && m.wordIndex == word.index) {
              qMod = m;
              break;
            }
          }
          if (qMod != null) break;
        }

        tokens.add(
          _UthmaniWordToken(
            controller: controller,
            word: word,
            surah: range.surah,
            ayahNumber: ayah.number,
            customEntry: customEntry,
            role: role,
            highlightOwner: highlightOwner,
            qiraatOverride: qMod,
          ),
        );
      }
      tokens.add(_UthmaniAyahEnd(number: ayah.number));
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (startsAtBeginning) _SurahOrnamentBanner(title: bundle.surahName),
        if (showBismillah)
          Padding(
            padding: const EdgeInsets.only(top: 10, bottom: 10),
            child: Text(
              'بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ',
              textAlign: TextAlign.center,
              textDirection: TextDirection.rtl,
              style: AppText.quran(
                size: controller.quranSize * 0.94,
                color: AppColors.forestDeep,
                height: 1.4,
              ),
            ),
          ),
        Wrap(
          textDirection: TextDirection.rtl,
          alignment: WrapAlignment.center,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 0,
          runSpacing: 12,
          children: tokens,
        ),
      ],
    );
  }
}

class _SurahOrnamentBanner extends StatelessWidget {
  const _SurahOrnamentBanner({required this.title});

  final String title;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.forestDeep.withOpacity(0.06),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.gold.withOpacity(0.75), width: 1.2),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.auto_awesome,
            size: 14,
            color: AppColors.gold.withOpacity(0.85),
          ),
          const SizedBox(width: 8),
          Text(
            title,
            style: AppText.ui(
              size: 16,
              weight: FontWeight.w700,
              color: AppColors.forestDeep,
              height: 1.2,
            ),
          ),
          const SizedBox(width: 8),
          Icon(
            Icons.auto_awesome,
            size: 14,
            color: AppColors.gold.withOpacity(0.85),
          ),
        ],
      ),
    );
  }
}

class _UthmaniWordToken extends StatelessWidget {
  const _UthmaniWordToken({
    required this.controller,
    required this.word,
    required this.surah,
    required this.ayahNumber,
    required this.customEntry,
    required this.role,
    this.highlightOwner,
    this.qiraatOverride,
  });

  final ReaderController controller;
  final AyahWord word;
  final int surah;
  final int ayahNumber;
  final MyMushafEntry? customEntry;
  final DemoSegmentRole role;
  final MyMushafEntry? highlightOwner;
  final QiraatWordOverride? qiraatOverride;

  @override
  Widget build(BuildContext context) {
    final hasCustom = customEntry != null;
    final uthmaniMark = word.inUthmaniMushaf ? word.uthmaniMark : null;
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
        wash = qMod != null ? qWash : Colors.transparent;
        marker = Colors.transparent;
    }

    Widget wordBox = DecoratedBox(
      key: role != DemoSegmentRole.none
          ? ValueKey<String>(
              'my-mushaf-hl-$surah-$ayahNumber-${word.index}-${role.name}',
            )
          : null,
      decoration: BoxDecoration(
        color: wash,
        borderRadius: BorderRadius.circular(6),
        border: Border(
          bottom: BorderSide(
            color: marker,
            width: 2.4,
          ),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 3, vertical: 1),
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
              child: wordBox,
            )
          : wordBox;
      wordBox = Tooltip(
        message: 'قراءة أخرى: ${qMod.modifiedWord} (في حفص: ${qMod.hafsWord})',
        waitDuration: const Duration(milliseconds: 250),
        child: painted,
      );
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 1),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        textDirection: TextDirection.rtl,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          if (highlightOwner != null)
            GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: () => _showSavedEntryDetailSheet(
                context,
                controller,
                highlightOwner!,
              ),
              child: wordBox,
            )
          else
            wordBox,
          if (uthmaniMark != null && uthmaniMark.isNotEmpty)
            Tooltip(
              message: word.uthmaniMarkName?.isNotEmpty == true
                  ? '${word.uthmaniMarkName} ($uthmaniMark)'
                  : 'علامة وقف بالمصحف ($uthmaniMark)',
              child: Padding(
                padding: const EdgeInsets.only(right: 2, bottom: 8),
                child: Text(
                  uthmaniMark,
                  textDirection: TextDirection.rtl,
                  style: AppText.ui(
                    size: (controller.quranSize * 0.44).clamp(10.0, 14.0),
                    weight: FontWeight.w700,
                    color: AppColors.forestDeep.withOpacity(0.82),
                    height: 1.0,
                  ),
                ),
              ),
            ),
          if (hasCustom)
            Padding(
              padding: const EdgeInsets.only(right: 3),
              child: StopBadge(
                key: ValueKey<String>('my-mushaf-badge-${customEntry!.stopId}'),
                symbol: customEntry!.symbol,
                verdictLabel: customEntry!.mark,
                compact: true,
                core: 22,
                selected: true,
                semanticsLabel:
                    'وقف مضاف إلى مصحفي عند ${customEntry!.word}'
                    '${customEntry!.scholar != null ? ' — ${customEntry!.scholar}' : ''}',
                onTap: () => _showSavedEntryDetailSheet(
                  context,
                  controller,
                  customEntry!,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _UthmaniAyahEnd extends StatelessWidget {
  const _UthmaniAyahEnd({required this.number});

  final int number;

  @override
  Widget build(BuildContext context) {
    return Container(
      constraints: const BoxConstraints(minWidth: 26, minHeight: 22),
      margin: const EdgeInsets.symmetric(horizontal: 2),
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: AppColors.gold.withOpacity(0.85)),
      ),
      child: Text(
        arabicDigits(number),
        textAlign: TextAlign.center,
        style: AppText.ui(
          size: 11,
          weight: FontWeight.w700,
          color: AppColors.forestDeep,
          height: 1.1,
        ),
      ),
    );
  }
}

Future<void> _showSavedEntryDetailSheet(
  BuildContext context,
  ReaderController controller,
  MyMushafEntry entry,
) async {
  final surahName = controller.surahNameForNumber(entry.surah);
  final page = controller.mushafPageForVerse(entry.surah, entry.ayah);
  final stop = controller.stopById(entry.stopId);
  final demo =
      stop == null ? null : controller.resolveMyMushafDemo(entry, stop);
  final waqfMeaning = demo?.meaningAtWaqf.trim() ?? '';
  final ibtidaMeaning = demo?.meaningAtIbtida.trim() ?? '';

  await showModalBottomSheet<void>(
    context: context,
    backgroundColor: Colors.transparent,
    builder: (sheetCtx) {
      return Directionality(
        textDirection: TextDirection.rtl,
        child: Container(
          decoration: const BoxDecoration(
            color: AppColors.sheet,
            borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
          ),
          padding: const EdgeInsets.fromLTRB(20, 14, 20, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Center(
                child: Container(
                  width: 38,
                  height: 4,
                  margin: const EdgeInsets.only(bottom: 14),
                  decoration: BoxDecoration(
                    color: AppColors.sheetLine,
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
              ),
              Row(
                children: [
                  StopBadge(
                    symbol: entry.symbol,
                    verdictLabel: entry.mark,
                    compact: true,
                    core: 30,
                    semanticsLabel: 'علامة الوقف ${entry.mark}',
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '«${entry.word}»',
                          style: AppText.quran(
                            size: 22,
                            color: AppColors.sheetText,
                            height: 1.3,
                          ),
                        ),
                        Text(
                          '$surahName • آية ${arabicDigits(entry.ayah)} • صفحة ${arabicDigits(page)}',
                          style: AppText.ui(
                            size: 12,
                            color: AppColors.sheetMuted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              if ((entry.scholar != null && entry.scholar!.isNotEmpty) ||
                  (entry.verdict != null && entry.verdict!.isNotEmpty) ||
                  waqfMeaning.isNotEmpty ||
                  ibtidaMeaning.isNotEmpty) ...[
                const SizedBox(height: 12),
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppColors.sheetRaised,
                    borderRadius: BorderRadius.circular(10),
                    border: Border.all(color: AppColors.sheetLine),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (entry.scholar != null && entry.scholar!.isNotEmpty)
                        Text(
                          'القول المختار: ${entry.scholar}',
                          style: AppText.ui(
                            size: 13,
                            weight: FontWeight.w700,
                            color: AppColors.goldSoft,
                          ),
                        ),
                      if (entry.verdict != null && entry.verdict!.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            entry.verdict!,
                            style: AppText.ui(
                              size: 13,
                              color: AppColors.sheetText,
                            ),
                          ),
                        ),
                      if (waqfMeaning.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: Text(
                            'عند الوقف: $waqfMeaning',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.ui(
                              size: 12,
                              color: AppColors.demoWaqfMarker,
                            ),
                          ),
                        ),
                      if (ibtidaMeaning.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: Text(
                            'عند الابتداء: $ibtidaMeaning',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: AppText.ui(
                              size: 12,
                              color: AppColors.approve,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ],
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () {
                        Navigator.of(sheetCtx).pop();
                        controller.removeFromMyMushaf(entry.stopId);
                      },
                      style: OutlinedButton.styleFrom(
                        foregroundColor: const Color(0xFFE8A0A0),
                        side: const BorderSide(color: Color(0x66E8A0A0)),
                      ),
                      icon: const Icon(Icons.bookmark_remove_outlined, size: 18),
                      label: Text(
                        'إزالة من مصحفي',
                        style: AppText.ui(
                          size: 13,
                          weight: FontWeight.w700,
                          color: const Color(0xFFE8A0A0),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: FilledButton.icon(
                      onPressed: () async {
                        Navigator.of(sheetCtx).pop();
                        var stop = controller.stopById(entry.stopId);
                        if (stop == null) {
                          await controller.loadSurah(entry.surah);
                          stop = controller.stopById(entry.stopId);
                        }
                        if (stop != null && context.mounted) {
                          await showWaqfSheet(
                            context,
                            controller,
                            stop.id,
                            includeDemos: true,
                          );
                        }
                      },
                      style: FilledButton.styleFrom(
                        backgroundColor: AppColors.goldSoft,
                        foregroundColor: AppColors.forestDeep,
                      ),
                      icon: const Icon(Icons.menu_book_outlined, size: 18),
                      label: Text(
                        'أقوال العلماء',
                        style: AppText.ui(
                          size: 13,
                          weight: FontWeight.w700,
                          color: AppColors.forestDeep,
                        ),
                      ),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      );
    },
  );
}

Future<void> _showSavedStopsSheet(
  BuildContext context,
  ReaderController controller, {
  required void Function(int page) onJumpToPage,
}) async {
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: Colors.transparent,
    builder: (sheetCtx) {
      return ListenableBuilder(
        listenable: controller,
        builder: (sheetCtx, _) {
          final entries = controller.sortedMyMushafStops;
          final maxH = MediaQuery.sizeOf(sheetCtx).height * 0.72;
          return Directionality(
            textDirection: TextDirection.rtl,
            child: Container(
              constraints: BoxConstraints(maxHeight: maxH),
              decoration: const BoxDecoration(
                color: AppColors.parchment,
                borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
              ),
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Center(
                    child: Container(
                      width: 38,
                      height: 4,
                      margin: const EdgeInsets.only(bottom: 12),
                      decoration: BoxDecoration(
                        color: AppColors.hairline,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                  ),
                  Row(
                    children: [
                      const Icon(
                        Icons.bookmarks_outlined,
                        size: 20,
                        color: AppColors.forestDeep,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'وقوفي المضافة إلى مصحفي (${arabicDigits(entries.length)})',
                          style: AppText.ui(
                            size: 16,
                            weight: FontWeight.w700,
                            color: AppColors.forestDeep,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  if (entries.isEmpty)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 28),
                      child: Text(
                        'لم تضف أي وقف بعد.\nمن تبويب «مصحف»، انقر أي موضع وقف واضغط «أضف لمصحفي» لإدراجه في مصحفك العثماني.',
                        textAlign: TextAlign.center,
                        style: AppText.ui(
                          size: 14,
                          color: AppColors.muted,
                          height: 1.6,
                        ),
                      ),
                    )
                  else
                    Flexible(
                      child: ListView.separated(
                        shrinkWrap: true,
                        itemCount: entries.length,
                        separatorBuilder: (_, __) =>
                            const Divider(height: 1, color: AppColors.hairline),
                        itemBuilder: (_, idx) {
                          final entry = entries[idx];
                          final surahName =
                              controller.surahNameForNumber(entry.surah);
                          final page = controller.mushafPageForVerse(
                            entry.surah,
                            entry.ayah,
                          );
                          return ListTile(
                            contentPadding: const EdgeInsets.symmetric(
                              horizontal: 4,
                              vertical: 4,
                            ),
                            leading: StopBadge(
                              symbol: entry.symbol,
                              verdictLabel: entry.mark,
                              compact: true,
                              core: 28,
                              semanticsLabel: entry.mark,
                            ),
                            title: Text(
                              '«${entry.word}»'
                              '${entry.scholar != null ? ' — ${entry.scholar}' : ''}',
                              style: AppText.ui(
                                size: 14,
                                weight: FontWeight.w700,
                                color: AppColors.ink,
                              ),
                            ),
                            subtitle: Text(
                              '$surahName • آية ${arabicDigits(entry.ayah)} • صفحة ${arabicDigits(page)}'
                              '${entry.verdict != null ? ' (${entry.verdict})' : ''}',
                              style: AppText.ui(
                                size: 12,
                                color: AppColors.muted,
                              ),
                            ),
                            trailing: IconButton(
                              tooltip: 'إزالة من مصحفي',
                              icon: const Icon(
                                Icons.delete_outline_rounded,
                                color: AppColors.muted,
                                size: 20,
                              ),
                              onPressed: () =>
                                  controller.removeFromMyMushaf(entry.stopId),
                            ),
                            onTap: () {
                              Navigator.of(sheetCtx).pop();
                              onJumpToPage(page);
                            },
                          );
                        },
                      ),
                    ),
                ],
              ),
            ),
          );
        },
      );
    },
  );
}

Future<void> _showPageJumperSheet(
  BuildContext context,
  ReaderController controller, {
  required void Function(int page) onSelectPage,
}) async {
  var selectedPage = controller.currentMushafPage.clamp(1, 604);
  final textCtrl = TextEditingController(text: selectedPage.toString());

  try {
    await showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (sheetCtx) {
        return StatefulBuilder(
          builder: (sheetCtx, setSheetState) {
            final maxH = MediaQuery.sizeOf(sheetCtx).height * 0.72;
            return Directionality(
              textDirection: TextDirection.rtl,
              child: Container(
                constraints: BoxConstraints(maxHeight: maxH),
                decoration: const BoxDecoration(
                  color: AppColors.parchment,
                  borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                ),
                padding: EdgeInsets.fromLTRB(
                  16,
                  12,
                  16,
                  16 + MediaQuery.viewInsetsOf(sheetCtx).bottom,
                ),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Center(
                      child: Container(
                        width: 38,
                        height: 4,
                        margin: const EdgeInsets.only(bottom: 12),
                        decoration: BoxDecoration(
                          color: AppColors.hairline,
                          borderRadius: BorderRadius.circular(2),
                        ),
                      ),
                    ),
                    Text(
                      'الانتقال في المصحف العثماني',
                      style: AppText.ui(
                        size: 16,
                        weight: FontWeight.w700,
                        color: AppColors.forestDeep,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: textCtrl,
                            keyboardType: TextInputType.number,
                            decoration: const InputDecoration(
                              isDense: true,
                              labelText: 'رقم الصفحة (١ – ٦٠٤)',
                              border: OutlineInputBorder(),
                            ),
                            onChanged: (val) {
                              final parsed = int.tryParse(val.trim());
                              if (parsed != null && parsed >= 1 && parsed <= 604) {
                                setSheetState(() => selectedPage = parsed);
                              }
                            },
                            onSubmitted: (val) {
                              final parsed = int.tryParse(val.trim());
                              if (parsed != null && parsed >= 1 && parsed <= 604) {
                                Navigator.of(sheetCtx).pop();
                                onSelectPage(parsed);
                              }
                            },
                          ),
                        ),
                        const SizedBox(width: 8),
                        FilledButton(
                          onPressed: () {
                            final parsed =
                                int.tryParse(textCtrl.text.trim()) ?? selectedPage;
                            final target = parsed.clamp(1, 604);
                            Navigator.of(sheetCtx).pop();
                            onSelectPage(target);
                          },
                          style: FilledButton.styleFrom(
                            backgroundColor: AppColors.forestDeep,
                          ),
                          child: Text(
                            'انتقال',
                            style: AppText.ui(
                              size: 13,
                              weight: FontWeight.w700,
                              color: AppColors.white,
                            ),
                          ),
                        ),
                      ],
                    ),
                    Slider(
                      value: selectedPage.toDouble(),
                      min: 1,
                      max: 604,
                      divisions: 603,
                      activeColor: AppColors.forestDeep,
                      label: 'ص ${arabicDigits(selectedPage)}',
                      onChanged: (v) {
                        final p = v.round();
                        setSheetState(() {
                          selectedPage = p;
                          textCtrl.text = p.toString();
                        });
                      },
                    ),
                    const Divider(height: 12, color: AppColors.hairline),
                    Text(
                      'أو اختر سورة:',
                      style: AppText.ui(
                        size: 12,
                        weight: FontWeight.w700,
                        color: AppColors.muted,
                      ),
                    ),
                    const SizedBox(height: 6),
                    Flexible(
                      child: ListView.builder(
                        shrinkWrap: true,
                        itemCount: controller.sampleSurahs.length,
                        itemBuilder: (_, idx) {
                          final s = controller.sampleSurahs[idx];
                          final startPage =
                              controller.firstMushafPageForSurah(s.number);
                          return ListTile(
                            dense: true,
                            visualDensity: VisualDensity.compact,
                            leading: Text(
                              arabicDigits(s.number),
                              style: AppText.ui(
                                size: 12,
                                weight: FontWeight.w700,
                                color: AppColors.forestDeep,
                              ),
                            ),
                            title: Text(
                              s.name,
                              style: AppText.ui(
                                size: 14,
                                weight: FontWeight.w600,
                                color: AppColors.ink,
                              ),
                            ),
                            trailing: Text(
                              'ص ${arabicDigits(startPage)}',
                              style: AppText.ui(
                                size: 12,
                                color: AppColors.muted,
                              ),
                            ),
                            onTap: () {
                              Navigator.of(sheetCtx).pop();
                              onSelectPage(startPage);
                            },
                          );
                        },
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  } finally {
    textCtrl.dispose();
  }
}
