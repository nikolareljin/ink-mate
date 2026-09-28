#pragma once

#include <array>
#include <cstddef>
#include <cstdint>

namespace inkmate::assets {

enum class IconPrimitive : std::uint8_t { Line, Circle, Rect, Box };
struct IconCommand { IconPrimitive primitive; int16_t a; int16_t b; int16_t c; int16_t d; int16_t width; };

inline constexpr std::array<IconCommand, 3> kCancelled{{
    {IconPrimitive::Circle, 100, 104, 35, 0, 3},
    {IconPrimitive::Line, 80, 84, 120, 124, 5},
    {IconPrimitive::Line, 120, 84, 80, 124, 5},
}};

inline constexpr std::array<IconCommand, 3> kConfirmation{{
    {IconPrimitive::Circle, 100, 104, 35, 0, 3},
    {IconPrimitive::Line, 78, 104, 94, 121, 5},
    {IconPrimitive::Line, 94, 121, 124, 86, 5},
}};

inline constexpr std::array<IconCommand, 4> kProcessing{{
    {IconPrimitive::Circle, 100, 104, 33, 0, 3},
    {IconPrimitive::Circle, 76, 104, 5, 0, 3},
    {IconPrimitive::Circle, 100, 104, 5, 0, 3},
    {IconPrimitive::Circle, 124, 104, 5, 0, 3},
}};

inline constexpr std::array<IconCommand, 5> kReady{{
    {IconPrimitive::Circle, 100, 104, 31, 0, 3},
    {IconPrimitive::Circle, 89, 96, 3, 0, 2},
    {IconPrimitive::Circle, 111, 96, 3, 0, 2},
    {IconPrimitive::Line, 84, 116, 100, 124, 3},
    {IconPrimitive::Line, 100, 124, 116, 116, 3},
}};

inline constexpr std::array<IconCommand, 6> kRecording{{
    {IconPrimitive::Box, 88, 76, 24, 39, 3},
    {IconPrimitive::Line, 72, 107, 72, 122, 3},
    {IconPrimitive::Line, 72, 122, 128, 122, 3},
    {IconPrimitive::Line, 128, 122, 128, 107, 3},
    {IconPrimitive::Line, 100, 122, 100, 140, 3},
    {IconPrimitive::Line, 83, 140, 117, 140, 3},
}};

inline constexpr std::array<IconCommand, 5> kSending{{
    {IconPrimitive::Line, 64, 109, 139, 75, 4},
    {IconPrimitive::Line, 139, 75, 112, 137, 4},
    {IconPrimitive::Line, 112, 137, 95, 111, 4},
    {IconPrimitive::Line, 95, 111, 64, 109, 4},
    {IconPrimitive::Line, 95, 111, 139, 75, 4},
}};

}  // namespace inkmate::assets
