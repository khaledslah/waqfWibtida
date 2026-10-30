import 'package:flutter/material.dart';

import '../data/sample_data.dart';
import '../models/waqf_models.dart';
import '../theme/app_theme.dart';
import '../widgets/ornament_divider.dart';
import '../widgets/stop_badge.dart';
import '../widgets/waqf_bottom_sheet.dart';

class MushafScreen extends StatelessWidget {
  const MushafScreen({super.key, required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const Padding(
          padding: EdgeInsets.only(top: 8),
          child: OrnamentDivider(),
        ),
        Expanded(
          child: yusufAyahs.isEmpty
              ? const _EmptyReading()
              : SingleChildScrollView(
                  padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
                  child: _ReadingBlock(controller: controller),
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

class _ReadingBlock extends StatelessWidget {
  const _ReadingBlock({required this.controller});

  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[];
    for (final ayah in yusufAyahs) {
      for (final word in ayah.words) {
        children.add(_WordToken(word: word, controller: controller));
      }
      children.add(_AyahMark(ayah.number));
    }

    return Wrap(
      textDirection: TextDirection.rtl,
      alignment: WrapAlignment.center,
      crossAxisAlignment: WrapCrossAlignment.center,
      spacing: 2,
      runSpacing: 14,
      children: children,
    );
  }
}

class _WordToken extends StatelessWidget {
  const _WordToken({required this.word, required this.controller});

  final AyahWord word;
  final ReaderController controller;

  @override
  Widget build(BuildContext context) {
    final stopId = word.stopId;
    final stop = stopId == null ? null : controller.stopById(stopId);
    final selected = stop != null && controller.selectedStopId == stop.id;
    final text = Text(
      word.text,
      textDirection: TextDirection.rtl,
      style: AppText.quran(
        size: controller.quranSize,
        color: AppColors.ink,
        height: 1.35,
      ),
    );

    return Row(
      mainAxisSize: MainAxisSize.min,
      textDirection: TextDirection.rtl,
      children: [
        DecoratedBox(
          decoration: BoxDecoration(
            color: selected ? AppColors.wordGlow : Colors.transparent,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 2, vertical: 1),
            child: text,
          ),
        ),
        if (stop != null)
          StopBadge(
            key: ValueKey<String>('stop-${stop.id}'),
            symbol: stop.symbol,
            selected: selected,
            semanticsLabel: 'وقف ${stop.label} عند ${stop.word}',
            onTap: () {
              controller.select(stop.id);
              showWaqfSheet(context, controller, stop.id);
            },
          ),
      ],
    );
  }
}

class _AyahMark extends StatelessWidget {
  const _AyahMark(this.number);

  final int number;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: 'آية ${arabicDigits(number)}',
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
          arabicDigits(number),
          style: AppText.ui(
            size: 10,
            weight: FontWeight.w700,
            color: AppColors.gold,
            height: 1.1,
          ),
        ),
      ),
    );
  }
}
