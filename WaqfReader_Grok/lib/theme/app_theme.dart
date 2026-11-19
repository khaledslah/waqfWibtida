import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

abstract final class AppColors {
  static const parchment = Color(0xFFF9F4E8);
  static const white = Color(0xFFFFFFFF);
  static const forest = Color(0xFF1A5C48);
  static const forestDeep = Color(0xFF1B3D2F);
  static const sheet = Color(0xFF1A2B20);
  static const sheetRaised = Color(0xFF24362B);
  static const sheetLine = Color(0xFF3C5346);
  static const gold = Color(0xFFA4843C);
  static const goldSoft = Color(0xFFC4A15A);
  static const ink = Color(0xFF1C1915);
  static const chipFill = Color(0xFFE5F2EB);
  static const badgeGreen = Color(0xFF1A5C48);
  static const badgeGreenRing = Color(0xFFB7D7C8);
  static const badgeGreenRingOuter = Color(0xFFD7EBE1);
  static const badgeGrey = Color(0xFFD5D2CB);
  static const badgeGreyText = Color(0xFF3E3E3E);
  static const badgeAmber = Color(0xFFD4A84B);
  static const approve = Color(0xFF7EAA90);
  static const navMuted = Color(0xFF8A918C);
  static const sheetText = Color(0xFFF6F3EA);
  static const sheetMuted = Color(0xFFD9D3C6);
  static const wordGlow = Color(0xFFF6E7C4);
  /// Continuous wash for demo waqf segment (pause span).
  static const demoWaqfWash = Color(0x59E8C878);
  /// Continuous wash for demo ibtida segment (resumption span).
  static const demoIbtidaWash = Color(0x4D8FCBB0);
  /// Marker line for demo waqf segment.
  static const demoWaqfMarker = Color(0xCCC4A15A);
  /// Marker line for demo ibtida segment.
  static const demoIbtidaMarker = Color(0xB31A5C48);
  /// Qira'at (non-Hafs) word swap: warm copper/terracotta paired with the
  /// dotted outline so swapped words harmonize with the parchment palette.
  static const qiraat = Color(0xFFB0602A);
  /// Lighter copper for dark panels.
  static const qiraatSoft = Color(0xFFE09F6E);
  /// Faint copper wash behind a swapped word outside any demo segment.
  static const qiraatWash = Color(0x14B0602A);

  /// User-selectable Qira'at highlight color presets (Settings sheet).
  static const List<QiraatColorOption> qiraatPresets = <QiraatColorOption>[
    QiraatColorOption(
      id: 'copper',
      label: 'نحاسي',
      color: Color(0xFFB0602A),
      wash: Color(0x14B0602A),
    ),
    QiraatColorOption(
      id: 'lapis',
      label: 'أزرق لازوردي',
      color: Color(0xFF28557F),
      wash: Color(0x1A28557F),
    ),
    QiraatColorOption(
      id: 'purple',
      label: 'بنفسجي ملكي',
      color: Color(0xFF6B3FA0),
      wash: Color(0x146B3FA0),
    ),
    QiraatColorOption(
      id: 'teal',
      label: 'فيروزي',
      color: Color(0xFF1E7F86),
      wash: Color(0x141E7F86),
    ),
    QiraatColorOption(
      id: 'burgundy',
      label: 'عنابي',
      color: Color(0xFF8A2E3B),
      wash: Color(0x148A2E3B),
    ),
    QiraatColorOption(
      id: 'indigo',
      label: 'نيلي',
      color: Color(0xFF3D3A8C),
      wash: Color(0x143D3A8C),
    ),
  ];

  static QiraatColorOption qiraatPresetById(String id) {
    for (final opt in qiraatPresets) {
      if (opt.id == id) return opt;
    }
    return qiraatPresets.first;
  }

  static const hairline = Color(0xFFE4DCC8);
  static const dash = Color(0xFF4A5850);
  static const muted = Color(0xFF7A756C);
  static const amberWash = Color(0xFFF8EFD6);
}

class QiraatColorOption {
  const QiraatColorOption({
    required this.id,
    required this.label,
    required this.color,
    required this.wash,
  });

  final String id;
  final String label;
  final Color color;
  final Color wash;
}

/// Shared palette for dock / sheet / bottom nav (معاني light vs أقوال dark).
class DockTone {
  const DockTone({
    required this.bg,
    required this.raised,
    required this.line,
    required this.text,
    required this.muted,
    required this.accent,
    required this.quran,
    required this.dark,
  });

  final Color bg;
  final Color raised;
  final Color line;
  final Color text;
  final Color muted;
  final Color accent;
  final Color quran;
  final bool dark;

  static const light = DockTone(
    bg: AppColors.parchment,
    raised: AppColors.white,
    line: AppColors.hairline,
    text: AppColors.ink,
    muted: AppColors.muted,
    accent: AppColors.forest,
    quran: AppColors.forestDeep,
    dark: false,
  );

  static const darkSheet = DockTone(
    bg: AppColors.sheet,
    raised: AppColors.sheetRaised,
    line: AppColors.sheetLine,
    text: AppColors.sheetText,
    muted: AppColors.sheetMuted,
    accent: AppColors.goldSoft,
    quran: AppColors.white,
    dark: true,
  );

  static DockTone of(bool dark) => dark ? darkSheet : light;
}

abstract final class AppText {
  static TextStyle ui({
    double size = 16,
    FontWeight weight = FontWeight.w500,
    Color color = AppColors.ink,
    double height = 1.45,
  }) {
    if (!GoogleFonts.config.allowRuntimeFetching) {
      return TextStyle(
        fontSize: size,
        fontWeight: weight,
        color: color,
        height: height,
      );
    }
    return GoogleFonts.cairo(
      fontSize: size,
      fontWeight: weight,
      color: color,
      height: height,
    );
  }

  /// Quran text in a monochrome (non-COLR) font. Amiri Quran paints its
  /// harakat in fixed red, so a text colour can't recolour them; this plain
  /// Amiri draws letters *and* marks in [color]. Used for Qira'at-changed
  /// letters so the changed i'rab really takes the highlight colour.
  static TextStyle quranPlain({
    double size = 26,
    FontWeight weight = FontWeight.w400,
    Color color = AppColors.ink,
    double height = 1.45,
  }) {
    if (!GoogleFonts.config.allowRuntimeFetching) {
      return TextStyle(
        fontSize: size,
        fontWeight: weight,
        color: color,
        height: height,
      );
    }
    return GoogleFonts.amiri(
      fontSize: size,
      fontWeight: weight,
      color: color,
      height: height,
    );
  }

  static TextStyle quran({
    double size = 26,
    FontWeight weight = FontWeight.w400,
    Color color = AppColors.ink,
    double height = 1.45,
  }) {
    if (!GoogleFonts.config.allowRuntimeFetching) {
      return TextStyle(
        fontSize: size,
        fontWeight: weight,
        color: color,
        height: height,
      );
    }
    return GoogleFonts.amiriQuran(
      fontSize: size,
      fontWeight: weight,
      color: color,
      height: height,
    );
  }
}

abstract final class AppTheme {
  static ThemeData light() {
    final base = ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme.fromSeed(
        seedColor: AppColors.forest,
        brightness: Brightness.light,
        primary: AppColors.forest,
        onPrimary: AppColors.white,
        secondary: AppColors.gold,
        onSecondary: AppColors.forestDeep,
        surface: AppColors.parchment,
        onSurface: AppColors.ink,
        error: const Color(0xFF8C3A32),
        onError: AppColors.white,
      ),
      scaffoldBackgroundColor: AppColors.parchment,
      splashFactory: InkRipple.splashFactory,
    );

    final cairo = GoogleFonts.config.allowRuntimeFetching
        ? GoogleFonts.cairoTextTheme(base.textTheme).apply(
            bodyColor: AppColors.ink,
            displayColor: AppColors.forestDeep,
          )
        : base.textTheme.apply(
            bodyColor: AppColors.ink,
            displayColor: AppColors.forestDeep,
          );

    return base.copyWith(
      textTheme: cairo,
      splashColor: AppColors.forest.withOpacity(0.08),
      highlightColor: AppColors.forest.withOpacity(0.04),
      dividerColor: AppColors.hairline,
      dialogTheme: DialogTheme(
        backgroundColor: AppColors.parchment,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        titleTextStyle: AppText.ui(
          size: 18,
          weight: FontWeight.w700,
          color: AppColors.forestDeep,
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: AppColors.forestDeep,
        contentTextStyle: AppText.ui(size: 14, color: AppColors.white),
        behavior: SnackBarBehavior.floating,
      ),
      popupMenuTheme: PopupMenuThemeData(
        color: AppColors.white,
        textStyle: AppText.ui(size: 15, color: AppColors.forestDeep),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: AppColors.parchment,
        surfaceTintColor: Colors.transparent,
        indicatorColor: AppColors.chipFill,
        height: 68,
        labelBehavior: NavigationDestinationLabelBehavior.alwaysShow,
        iconTheme: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return IconThemeData(
            color: selected ? AppColors.forest : AppColors.navMuted,
            size: 24,
          );
        }),
        labelTextStyle: WidgetStateProperty.resolveWith((states) {
          final selected = states.contains(WidgetState.selected);
          return AppText.ui(
            size: 12,
            weight: selected ? FontWeight.w700 : FontWeight.w500,
            color: selected ? AppColors.forest : AppColors.navMuted,
            height: 1.2,
          );
        }),
      ),
    );
  }
}
