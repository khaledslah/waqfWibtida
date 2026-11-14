import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../utils/book_page_service.dart';
import '../utils/waqf_share.dart';
import 'page_image_viewer.dart';
import 'stop_badge.dart';

Future<void> showWaqfSheet(
  BuildContext context,
  ReaderController controller,
  String stopId, {
  bool includeDemos = false,
}) {
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    isDismissible: true,
    enableDrag: true,
    backgroundColor: Colors.transparent,
    barrierColor: const Color(0x99000000),
    builder: (context) {
      return WaqfBottomSheet(
        controller: controller,
        stopId: stopId,
        includeDemos: includeDemos,
      );
    },
  );
}

/// Confirms with the user before submitting or cancelling a stop report.
Future<void> confirmAndToggleStopReport(
  BuildContext context,
  ReaderController controller,
  String stopId,
) async {
  final willAdd = !controller.isSent(stopId);
  final stop = controller.stopById(stopId);
  final stopLabel = stop == null
      ? ''
      : '\n﴿${stop.word}﴾ — ${controller.currentSurahName}، آية ${arabicDigits(stop.ayah)}';

  final confirmed = await showDialog<bool>(
    context: context,
    builder: (dialogContext) => Directionality(
      textDirection: TextDirection.rtl,
      child: AlertDialog(
        title: Text(
          willAdd ? 'تأكيد إرسال الإبلاغ' : 'تأكيد إلغاء الإبلاغ',
          style: AppText.ui(
            size: 17,
            weight: FontWeight.w700,
            color: AppColors.forestDeep,
          ),
        ),
        content: Text(
          willAdd
              ? 'هل تريد إرسال هذا الموضع للمراجعة والإبلاغ؟$stopLabel'
              : 'هل تريد إزالة هذا الموضع من قائمة المراجعة والإبلاغ؟$stopLabel',
          style: AppText.ui(size: 14, color: AppColors.ink),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(
              'إلغاء',
              style: AppText.ui(size: 14, color: AppColors.muted),
            ),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(
              willAdd ? 'تأكيد الإرسال' : 'تأكيد الإزالة',
              style: AppText.ui(
                size: 14,
                weight: FontWeight.w700,
                color: AppColors.white,
              ),
            ),
          ),
        ],
      ),
    ),
  );

  if (confirmed != true || !context.mounted) return;
  await controller.toggleSent(stopId);
  if (!context.mounted) return;
  ScaffoldMessenger.maybeOf(context)?.showSnackBar(
    SnackBar(
      behavior: SnackBarBehavior.floating,
      duration: const Duration(seconds: 2),
      margin: const EdgeInsets.fromLTRB(16, 0, 16, 32),
      content: Text(
        willAdd
            ? 'أُضيف الوقف إلى قائمة المراجعة والإبلاغ'
            : 'أُزيل الوقف من قائمة المراجعة',
        style: AppText.ui(size: 14, color: AppColors.white),
      ),
    ),
  );
}

class WaqfBottomSheet extends StatefulWidget {
  const WaqfBottomSheet({
    super.key,
    required this.controller,
    required this.stopId,
    this.includeDemos = false,
  });

  final ReaderController controller;
  final String stopId;

  /// When false (normal badge tap), hide demosAndMeanings / ibtida cards.
  final bool includeDemos;

  @override
  State<WaqfBottomSheet> createState() => _WaqfBottomSheetState();
}

class _WaqfBottomSheetState extends State<WaqfBottomSheet> {
  Future<void> _openPage(int? page) async {
    if (page == null) return;
    await showSajawandiPage(context, page: page);
  }

  void _dismiss() {
    if (Navigator.of(context).canPop()) {
      Navigator.of(context).pop();
    }
  }

  @override
  Widget build(BuildContext context) {
    final height = MediaQuery.sizeOf(context).height * 0.72;
    final bottom = MediaQuery.paddingOf(context).bottom;

    // Align expands to fill the modal; absorb empty space so outside taps
    // and Android back (PopScope) reliably dismiss.
    return PopScope(
      canPop: true,
      child: Stack(
        children: [
          Positioned.fill(
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTap: _dismiss,
              child: const ColoredBox(color: Colors.transparent),
            ),
          ),
          Align(
            alignment: Alignment.bottomCenter,
            child: Material(
              color: AppColors.sheet,
              borderRadius:
                  const BorderRadius.vertical(top: Radius.circular(28)),
              clipBehavior: Clip.antiAlias,
              child: SizedBox(
                height: height,
                child: ListenableBuilder(
                  listenable: widget.controller,
                  builder: (context, _) {
                    final stop = widget.controller.stopById(widget.stopId);
                    if (stop == null) return const _MissingStop();
                    final sent = widget.controller.isSent(stop.id);
                    final fav = widget.controller.isFavorite(stop.id);
                    return Column(
                      children: [
                        const _DragHandle(),
                        Expanded(
                          child: SelectionArea(
                            child: SingleChildScrollView(
                              padding: EdgeInsets.fromLTRB(
                                20,
                                4,
                                20,
                                20 + bottom,
                              ),
                              child: WaqfStopSheetBody(
                                controller: widget.controller,
                                stop: stop,
                                selectedScholar:
                                    widget.controller.selectedScholar,
                                includeDemos: widget.includeDemos,
                                isVerseEnd:
                                    widget.controller.isVerseEnd(stop),
                                favorite: fav,
                                sent: sent,
                                onToggleFavorite: () => widget.controller
                                    .toggleFavorite(stop.id),
                                onToggleReport: () =>
                                    confirmAndToggleStopReport(
                                      context,
                                      widget.controller,
                                      stop.id,
                                    ),
                                onOpenPage: _openPage,
                              ),
                            ),
                          ),
                        ),
                      ],
                    );
                  },
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// Stop share menu: أقوال / معاني / الكل (no copy in the list).
class WaqfStopShareMenu extends StatelessWidget {
  const WaqfStopShareMenu({
    super.key,
    required this.controller,
    required this.stop,
    required this.tone,
  });

  final ReaderController controller;
  final WaqfStop stop;
  final DockTone tone;

  void _share(BuildContext context, StopShareMode mode) {
    final text = formatStopShare(
      stop,
      mode: mode,
      ayah: ayahForStop(controller, stop),
      surahName: controller.currentSurahName,
      highlightDemo: shareHighlightDemo(controller, stop),
    );
    shareText(context, text, subject: 'وقف: ${stop.word}');
  }

  @override
  Widget build(BuildContext context) {
    final hasMeanings = stop.hasDemosAndMeanings;
    return PopupMenuButton<StopShareMode>(
      tooltip: 'مشاركة الوقف',
      icon: Icon(Icons.share_outlined, color: tone.muted),
      color: tone.raised,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: tone.line),
      ),
      onSelected: (mode) => _share(context, mode),
      itemBuilder: (context) => [
        PopupMenuItem(
          value: StopShareMode.opinions,
          child: Text(
            'آراء العلماء',
            style: AppText.ui(size: 13, color: tone.text),
          ),
        ),
        PopupMenuItem(
          value: StopShareMode.meanings,
          enabled: hasMeanings,
          child: Text(
            'المعاني',
            style: AppText.ui(
              size: 13,
              color: hasMeanings ? tone.text : tone.muted,
            ),
          ),
        ),
        PopupMenuItem(
          value: StopShareMode.all,
          child: Text(
            'الكل',
            style: AppText.ui(size: 13, color: tone.text),
          ),
        ),
      ],
    );
  }
}

class _DragHandle extends StatelessWidget {
  const _DragHandle();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Container(
        width: 40,
        height: 4,
        margin: const EdgeInsets.only(top: 10, bottom: 12),
        decoration: BoxDecoration(
          color: AppColors.white.withOpacity(0.45),
          borderRadius: BorderRadius.circular(4),
        ),
      ),
    );
  }
}

/// Shared opinions sheet content (pages, share, flags) for modal + dock.
class WaqfStopSheetBody extends StatelessWidget {
  const WaqfStopSheetBody({
    super.key,
    required this.controller,
    required this.stop,
    required this.selectedScholar,
    required this.includeDemos,
    required this.isVerseEnd,
    required this.favorite,
    required this.sent,
    required this.onToggleFavorite,
    required this.onToggleReport,
    required this.onOpenPage,
    this.showAiSection = true,
    this.dark = true,
  });

  final ReaderController controller;
  final WaqfStop stop;
  final String? selectedScholar;
  final bool includeDemos;
  final bool isVerseEnd;
  final bool favorite;
  final bool sent;
  final VoidCallback onToggleFavorite;
  final VoidCallback onToggleReport;
  final Future<void> Function(int? page) onOpenPage;
  final bool showAiSection;
  final bool dark;

  @override
  Widget build(BuildContext context) {
    final tone = DockTone.of(dark);
    final activeOp = stop.opinionForScholar(selectedScholar);
    final activeSymbol = stop.symbolForScholar(selectedScholar);
    final activeVerdictLabel = stop.verdictLabelForScholar(selectedScholar);
    final activeIsQila = stop.isQilaForScholar(selectedScholar);
    final activeLabel = stop.labelForScholar(selectedScholar);
    final activeReason = stop.reasonForScholar(selectedScholar);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            StopBadge(
              symbol: activeSymbol,
              verdictLabel: activeVerdictLabel,
              isQila: activeIsQila,
              semanticsLabel: '$activeLabel ${stop.word}',
              core: 36,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    activeLabel,
                    style: AppText.ui(
                      size: 18,
                      weight: FontWeight.w700,
                      color: dark
                          ? const Color(0xFFE7F6EE)
                          : AppColors.forestDeep,
                    ),
                  ),
                  if (activeOp != null)
                    Text(
                      '${activeOp.scholar} (${activeOp.book})',
                      style: AppText.ui(
                        size: 12,
                        color: tone.muted,
                      ),
                    ),
                ],
              ),
            ),
            IconButton(
              tooltip: favorite ? 'إزالة من المفضلة' : 'إضافة للمفضلة',
              onPressed: onToggleFavorite,
              icon: Icon(
                favorite ? Icons.favorite : Icons.favorite_border,
                color: favorite ? const Color(0xFFE8A0A0) : tone.muted,
              ),
            ),
            IconButton(
              tooltip: sent ? 'في قائمة المراجعة (انقر للإلغاء)' : 'إبلاغ / إضافة للمراجعة',
              onPressed: onToggleReport,
              icon: Icon(
                sent ? Icons.flag_rounded : Icons.outlined_flag_rounded,
                color: sent ? const Color(0xFFE2A44B) : tone.muted,
              ),
            ),
            WaqfStopShareMenu(
              controller: controller,
              stop: stop,
              tone: tone,
            ),
          ],
        ),
        const SizedBox(height: 4),
        Text(
          stop.word,
          textAlign: TextAlign.start,
          style: AppText.quran(
            size: 40,
            weight: FontWeight.w700,
            color: tone.quran,
            height: 1.3,
          ),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            if (isVerseEnd) _SheetTag(text: 'رأس آية', tone: tone),
            if (stop.inUthmaniMushaf)
              _SheetTag(text: 'في المصحف العثماني', tone: tone),
            if (activeOp != null && activeOp.verdicts.length > 1)
              _SheetTag(
                text: '${arabicDigits(activeOp.verdicts.length)} أوجه للعالم',
                tone: tone,
              ),
          ],
        ),
        const SizedBox(height: 12),
        Text(
          activeReason,
          textAlign: TextAlign.start,
          style: AppText.ui(
            size: 15,
            weight: FontWeight.w500,
            color: tone.text,
            height: 1.75,
          ),
        ),
        const SizedBox(height: 20),
        _SectionTitle(
          icon: Icons.menu_book_outlined,
          title: 'أقوال أئمة الوقف والابتداء',
          tone: tone,
        ),
        const SizedBox(height: 8),
        _OpinionTable(
          controller: controller,
          stop: stop,
          opinions: stop.opinions,
          includeDemos: includeDemos,
          emptyText: 'لا حكم مسجّل.',
          sajawandiPage: stop.textPage,
          onOpenPage: onOpenPage,
          tone: tone,
        ),
        if (showAiSection) ...[
          const SizedBox(height: 16),
          _AiDemoMeaningsSection(
            controller: controller,
            stop: stop,
            selectedScholar: selectedScholar,
          ),
        ],
      ],
    );
  }
}

/// Embeddable scrollable opinions panel (same content as the modal sheet).
class WaqfStopSheetPanel extends StatefulWidget {
  const WaqfStopSheetPanel({
    super.key,
    required this.controller,
    required this.stopId,
    this.includeDemos = false,
    this.showAiSection = false,
    this.dark = true,
  });

  final ReaderController controller;
  final String stopId;
  final bool includeDemos;
  final bool showAiSection;
  final bool dark;

  @override
  State<WaqfStopSheetPanel> createState() => _WaqfStopSheetPanelState();
}

class _WaqfStopSheetPanelState extends State<WaqfStopSheetPanel> {
  Future<void> _openPage(int? page) async {
    if (page == null) return;
    await showSajawandiPage(context, page: page);
  }

  @override
  Widget build(BuildContext context) {
    final bottom = MediaQuery.paddingOf(context).bottom;
    final tone = DockTone.of(widget.dark);
    return Material(
      color: tone.bg,
      child: ListenableBuilder(
        listenable: widget.controller,
        builder: (context, _) {
          final stop = widget.controller.stopById(widget.stopId);
          if (stop == null) {
            return Center(
              child: Text(
                'الوقف غير موجود',
                style: AppText.ui(size: 14, color: tone.muted),
              ),
            );
          }
          final sent = widget.controller.isSent(stop.id);
          final fav = widget.controller.isFavorite(stop.id);
          return SelectionArea(
            child: SingleChildScrollView(
              padding: EdgeInsets.fromLTRB(16, 8, 16, 16 + bottom),
              child: WaqfStopSheetBody(
                controller: widget.controller,
                stop: stop,
                selectedScholar: widget.controller.selectedScholar,
                includeDemos: widget.includeDemos,
                isVerseEnd: widget.controller.isVerseEnd(stop),
                favorite: fav,
                sent: sent,
                onToggleFavorite: () =>
                    widget.controller.toggleFavorite(stop.id),
                onToggleReport: () => confirmAndToggleStopReport(
                  context,
                  widget.controller,
                  stop.id,
                ),
                onOpenPage: _openPage,
                showAiSection: widget.showAiSection,
                dark: widget.dark,
              ),
            ),
          );
        },
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle({
    required this.icon,
    required this.title,
    required this.tone,
  });

  final IconData icon;
  final String title;
  final DockTone tone;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 18, color: tone.accent),
        const SizedBox(width: 8),
        Expanded(
          child: Text(
            title,
            style: AppText.ui(
              size: 15,
              weight: FontWeight.w700,
              color: tone.text,
            ),
          ),
        ),
      ],
    );
  }
}

class _OpinionTable extends StatelessWidget {
  const _OpinionTable({
    required this.controller,
    required this.stop,
    required this.opinions,
    required this.includeDemos,
    required this.emptyText,
    required this.sajawandiPage,
    required this.onOpenPage,
    required this.tone,
  });

  final ReaderController controller;
  final WaqfStop stop;
  final List<ScholarOpinion> opinions;
  final bool includeDemos;
  final String emptyText;
  final int? sajawandiPage;
  final Future<void> Function(int? page) onOpenPage;
  final DockTone tone;

  @override
  Widget build(BuildContext context) {
    if (opinions.isEmpty) {
      return Text(
        emptyText,
        style: AppText.ui(size: 14, color: tone.muted),
      );
    }

    return DecoratedBox(
      decoration: BoxDecoration(
        color: tone.raised,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: tone.line),
      ),
      child: Column(
        children: [
          for (var i = 0; i < opinions.length; i++) ...[
            if (i > 0) Divider(height: 1, thickness: 1, color: tone.line),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              child: _OpinionRow(
                controller: controller,
                stop: stop,
                opinion: opinions[i],
                includeDemos: includeDemos,
                sajawandiPage: sajawandiPage,
                onOpenPage: onOpenPage,
                tone: tone,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _OpinionRow extends StatelessWidget {
  const _OpinionRow({
    required this.controller,
    required this.stop,
    required this.opinion,
    required this.includeDemos,
    required this.sajawandiPage,
    required this.onOpenPage,
    required this.tone,
  });

  final ReaderController controller;
  final WaqfStop stop;
  final ScholarOpinion opinion;
  final bool includeDemos;
  final int? sajawandiPage;
  final Future<void> Function(int? page) onOpenPage;
  final DockTone tone;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Expanded(
              flex: 3,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    opinion.scholar,
                    textAlign: TextAlign.start,
                    style: AppText.ui(
                      size: 14,
                      weight: FontWeight.w700,
                      color: tone.text,
                    ),
                  ),
                  if (opinion.targetWord.trim().isNotEmpty)
                    Text(
                      '«${opinion.targetWord}»',
                      textAlign: TextAlign.start,
                      style: AppText.ui(
                        size: 11,
                        color: tone.muted,
                      ),
                    ),
                ],
              ),
            ),
            Expanded(
              flex: 5,
              child: Wrap(
                spacing: 6,
                runSpacing: 6,
                alignment: WrapAlignment.center,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  for (var i = 0; i < opinion.verdicts.length; i++)
                    _VerdictFacePill(
                      verdict: opinion.verdicts[i],
                      verdictLabel: i < opinion.verdictLabels.length
                          ? opinion.verdictLabels[i]
                          : opinion.primaryVerdictLabel,
                      symbol: i < opinion.symbols.length
                          ? opinion.symbols[i]
                          : opinion.primarySymbol,
                      isQila: i < opinion.isQila.length
                          ? opinion.isQila[i]
                          : false,
                      tone: tone,
                    ),
                ],
              ),
            ),
            Expanded(
              flex: 3,
              child: Align(
                alignment: AlignmentDirectional.centerEnd,
                child: _PageRef(
                  surah: stop.surah,
                  ayah: stop.ayah,
                  opinion: opinion,
                  sajawandiPage: sajawandiPage,
                  onOpenPage: onOpenPage,
                  tone: tone,
                ),
              ),
            ),
          ],
        ),
        if (opinion.comment != null && opinion.comment!.trim().isNotEmpty) ...[
          const SizedBox(height: 8),
          Text(
            opinion.comment!,
            textAlign: TextAlign.start,
            style: AppText.ui(
              size: 13,
              color: tone.text.withOpacity(0.9),
              height: 1.55,
            ),
          ),
        ],
        if (includeDemos && opinion.demosAndMeanings.isNotEmpty) ...[
          const SizedBox(height: 10),
          for (var d = 0; d < opinion.demosAndMeanings.length; d++) ...[
            if (d > 0) const SizedBox(height: 8),
            _DemoMeaningCard(
              demo: opinion.demosAndMeanings[d],
              selected: identical(
                controller.activeDemoHighlight,
                opinion.demosAndMeanings[d],
              ),
              onTap: () {
                controller.select(stop.id);
                controller.selectDemo(
                  scholar: opinion.scholar,
                  demoIndex: d,
                );
              },
            ),
          ],
        ],
        Padding(
          padding: const EdgeInsets.only(top: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.end,
            children: [
              InkWell(
                onTap: () {
                  final text = formatOpinionText(
                    stop,
                    opinion,
                    surahName: controller.currentSurahName,
                  );
                  copyText(
                    context,
                    text,
                    message: 'تم نسخ قول ${opinion.scholar}',
                  );
                },
                borderRadius: BorderRadius.circular(6),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.copy_rounded,
                        size: 14,
                        color: tone.dark ? AppColors.goldSoft : tone.muted,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        'نسخ',
                        style: AppText.ui(
                          size: 11,
                          color: tone.dark ? AppColors.goldSoft : tone.muted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(width: 8),
              InkWell(
                onTap: () {
                  final text = formatOpinionText(
                    stop,
                    opinion,
                    surahName: controller.currentSurahName,
                  );
                  shareText(
                    context,
                    text,
                    subject: 'وقف ${stop.word} عند ${opinion.scholar}',
                  );
                },
                borderRadius: BorderRadius.circular(6),
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 4,
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Icon(
                        Icons.share_outlined,
                        size: 14,
                        color: tone.dark ? AppColors.goldSoft : tone.muted,
                      ),
                      const SizedBox(width: 4),
                      Text(
                        'مشاركة',
                        style: AppText.ui(
                          size: 11,
                          color: tone.dark ? AppColors.goldSoft : tone.muted,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _DemoMeaningCard extends StatelessWidget {
  const _DemoMeaningCard({
    required this.demo,
    required this.selected,
    required this.onTap,
  });

  final WaqfDemoAndMeaning demo;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final verdictTag = (demo.isQila && !demo.verdict.contains('قيل'))
        ? 'قيل: ${demo.verdict}'
        : demo.verdict;
    final attr = demo.attributedTo?.trim();
    final title = (attr != null && attr.isNotEmpty)
        ? 'بيان الوقف والابتداء · $verdictTag — $attr'
        : 'بيان الوقف والابتداء · $verdictTag';

    final rows = <(String, String)>[
      if (demo.waqfDemo.trim().isNotEmpty) ('الوقف', demo.waqfDemo.trim()),
      if (demo.ibtidaDemo.trim().isNotEmpty) ('الابتداء', demo.ibtidaDemo.trim()),
      if (demo.meaningAtWaqf.trim().isNotEmpty)
        ('المعنى عند الوقف', demo.meaningAtWaqf.trim()),
      if (demo.meaningAtIbtida.trim().isNotEmpty)
        ('المعنى عند الابتداء', demo.meaningAtIbtida.trim()),
      if (demo.meaningIfConnected.trim().isNotEmpty)
        ('المعنى عند الوصل', demo.meaningIfConnected.trim()),
    ];

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(10),
        child: DecoratedBox(
          decoration: BoxDecoration(
            color: selected
                ? AppColors.goldSoft.withOpacity(0.12)
                : AppColors.sheet,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(
              color: selected
                  ? AppColors.goldSoft
                  : (demo.isQila
                      ? AppColors.goldSoft.withOpacity(0.55)
                      : AppColors.sheetLine),
              width: selected ? 1.4 : 1,
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(10, 8, 10, 10),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        title,
                        style: AppText.ui(
                          size: 12,
                          weight: FontWeight.w700,
                          color: AppColors.goldSoft,
                        ),
                      ),
                    ),
                    if (selected) ...[
                      const _DemoLegendDot(
                        color: AppColors.demoWaqfMarker,
                        label: 'وقف',
                      ),
                      const SizedBox(width: 6),
                      const _DemoLegendDot(
                        color: AppColors.demoIbtidaMarker,
                        label: 'ابتداء',
                      ),
                    ],
                  ],
                ),
                for (final row in rows) ...[
                  const SizedBox(height: 6),
                  Text(
                    row.$1,
                    style: AppText.ui(
                      size: 11,
                      weight: FontWeight.w600,
                      color: AppColors.sheetMuted,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    row.$2,
                    textAlign: TextAlign.start,
                    style: AppText.ui(
                      size: 13,
                      color: AppColors.sheetText,
                      height: 1.55,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _DemoLegendDot extends StatelessWidget {
  const _DemoLegendDot({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 3,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(2),
          ),
        ),
        const SizedBox(width: 4),
        Text(
          label,
          style: AppText.ui(
            size: 10,
            weight: FontWeight.w600,
            color: AppColors.sheetMuted,
          ),
        ),
      ],
    );
  }
}

class _VerdictFacePill extends StatelessWidget {
  const _VerdictFacePill({
    required this.verdict,
    required this.verdictLabel,
    required this.symbol,
    required this.isQila,
    required this.tone,
  });

  final String verdict;
  final String verdictLabel;
  final StopSymbol symbol;
  final bool isQila;
  final DockTone tone;

  @override
  Widget build(BuildContext context) {
    final displayVerdict =
        (isQila && !verdict.contains('قيل')) ? 'قيل: $verdict' : verdict;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: tone.bg,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isQila ? tone.accent.withOpacity(0.75) : tone.line,
        ),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          IgnorePointer(
            child: StopBadge(
              symbol: symbol,
              verdictLabel: verdictLabel,
              isQila: isQila,
              semanticsLabel: displayVerdict,
              core: 20,
            ),
          ),
          const SizedBox(width: 4),
          Flexible(
            child: Text(
              displayVerdict,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppText.ui(
                size: 12,
                weight: FontWeight.w600,
                color: tone.text,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _PageRef extends StatelessWidget {
  const _PageRef({
    required this.surah,
    required this.ayah,
    required this.opinion,
    required this.sajawandiPage,
    required this.onOpenPage,
    required this.tone,
  });

  final int surah;
  final int ayah;
  final ScholarOpinion opinion;
  final int? sajawandiPage;
  final Future<void> Function(int? page) onOpenPage;
  final DockTone tone;

  @override
  Widget build(BuildContext context) {
    final pageStr = opinion.page;
    final bookKey =
        bookKeyForScholar(scholar: opinion.scholar, book: opinion.book);
    final hasBookLink = bookKey != null &&
        (pageStr != null ||
            (bookKey == 'sajawandi' && sajawandiPage != null) ||
            bookKey == 'nahhas');

    if (pageStr == null && !hasBookLink) {
      return Semantics(
        label: '${opinion.book}، بدون رقم صفحة',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              opinion.book,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: AppText.ui(size: 11, color: tone.muted),
            ),
            const SizedBox(height: 2),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
              decoration: BoxDecoration(
                color: tone.dark ? AppColors.dash : AppColors.hairline,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Text(
                '−',
                style: AppText.ui(
                  size: 14,
                  color: tone.muted,
                  height: 1.2,
                ),
              ),
            ),
          ],
        ),
      );
    }

    final displayRef = pageStr ?? 'آية ${arabicDigits(ayah)}';
    // Light: muted (synced with نسخ/مشاركة). Dark: gold.
    final linkColor = tone.dark ? AppColors.goldSoft : tone.muted;

    final refRow = Row(
      mainAxisSize: MainAxisSize.min,
      textDirection: TextDirection.ltr,
      children: [
        Flexible(
          child: Text(
            displayRef,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: AppText.ui(
              size: 14,
              weight: hasBookLink ? FontWeight.w700 : FontWeight.w500,
              color: hasBookLink ? linkColor : tone.text,
            ),
          ),
        ),
        const SizedBox(width: 4),
        Icon(
          Icons.menu_book_outlined,
          size: 16,
          color: hasBookLink ? linkColor : tone.muted,
        ),
      ],
    );

    final body = Column(
      crossAxisAlignment: CrossAxisAlignment.end,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          opinion.book,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          textAlign: TextAlign.end,
          style: AppText.ui(
            size: 11,
            color: hasBookLink
                ? (tone.dark ? linkColor.withOpacity(0.85) : tone.muted)
                : tone.muted,
          ),
        ),
        const SizedBox(height: 2),
        refRow,
      ],
    );

    return Semantics(
      button: true,
      label: 'عرض صفحة ${opinion.book} $displayRef',
      child: InkWell(
        onTap: () {
          showScholarBookPage(
            context,
            scholar: opinion.scholar,
            book: opinion.book,
            pageStr: opinion.page,
            sajawandiPage: sajawandiPage,
            surah: surah,
            ayah: ayah,
          );
        },
        borderRadius: BorderRadius.circular(8),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 2),
          child: body,
        ),
      ),
    );
  }
}

/// Always-visible AI-inferred waqf meanings (full demo cards).
class _AiDemoMeaningsSection extends StatelessWidget {
  const _AiDemoMeaningsSection({
    required this.controller,
    required this.stop,
    required this.selectedScholar,
  });

  final ReaderController controller;
  final WaqfStop stop;
  final String? selectedScholar;

  List<(ScholarOpinion, int, WaqfDemoAndMeaning)> _entries() {
    final out = <(ScholarOpinion, int, WaqfDemoAndMeaning)>[];
    ScholarOpinion? preferred;
    if (selectedScholar != null && selectedScholar!.isNotEmpty) {
      final op = stop.opinionForScholar(selectedScholar);
      if (op != null && op.demosAndMeanings.isNotEmpty) preferred = op;
    }
    final opinions = preferred != null
        ? <ScholarOpinion>[preferred]
        : stop.opinions.where((o) => o.demosAndMeanings.isNotEmpty).toList();
    for (final op in opinions) {
      for (var d = 0; d < op.demosAndMeanings.length; d++) {
        out.add((op, d, op.demosAndMeanings[d]));
      }
    }
    return out;
  }

  @override
  Widget build(BuildContext context) {
    final entries = _entries();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const _SectionTitle(
          icon: Icons.auto_awesome,
          title: 'معاني وقف (مستنتجة AI)',
          tone: DockTone.darkSheet,
        ),
        const SizedBox(height: 8),
        if (entries.isEmpty)
          Text(
            'لا معاني مقترحة لهذا الوقف.',
            textAlign: TextAlign.start,
            style: AppText.ui(
              size: 14,
              color: AppColors.sheetMuted,
              height: 1.5,
            ),
          )
        else
          for (var i = 0; i < entries.length; i++) ...[
            if (i > 0) const SizedBox(height: 8),
            _DemoMeaningCard(
              demo: entries[i].$3,
              selected: controller.demoHighlightActive &&
                  controller.selectedStopId == stop.id &&
                  identical(
                    controller.activeDemoHighlight,
                    entries[i].$3,
                  ),
              onTap: () {
                controller.activateDemoHighlight(
                  stop.id,
                  scholar: entries[i].$1.scholar,
                  demoIndex: entries[i].$2,
                );
              },
            ),
          ],
      ],
    );
  }
}


class _SheetTag extends StatelessWidget {
  const _SheetTag({required this.text, required this.tone});

  final String text;
  final DockTone tone;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: tone.raised,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: tone.accent.withOpacity(0.55)),
      ),
      child: Text(
        text,
        style: AppText.ui(
          size: 11,
          weight: FontWeight.w700,
          color: tone.accent,
          height: 1.1,
        ),
      ),
    );
  }
}

class _MissingStop extends StatelessWidget {
  const _MissingStop();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Text(
            'تعذر فتح هذا الوقف.',
            textAlign: TextAlign.center,
            style: AppText.ui(size: 16, color: AppColors.sheetText),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: () => Navigator.of(context).pop(),
            style: FilledButton.styleFrom(backgroundColor: AppColors.approve),
            child: Text(
              'إغلاق',
              style: AppText.ui(color: AppColors.white, weight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}
