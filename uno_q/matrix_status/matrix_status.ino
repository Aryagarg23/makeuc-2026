// Shows the current content bucket (digit 0-9, left) and stimulus intensity
// (vertical bar, right) on the UNO Q 8x13 LED matrix.
// Linux side calls these over the Arduino Router (msgpack-rpc):
//   show(bucket_index:int, intensity:float)   bucket 0..9, intensity 0..1
//   clear()
// provide_safe() makes the handlers run in loop() context, which is where
// the LED matrix driver must be touched.
#include <Arduino_LED_Matrix.h>
#include "Arduino_RouterBridge.h"

static const int ROWS = 8;
static const int COLS = 13;

// 3 wide x 5 tall digits, one row per entry, bit 2 = left column.
static const uint8_t DIGITS[10][5] = {
  {7,5,5,5,7}, {2,6,2,2,7}, {7,1,7,4,7}, {7,1,7,1,7}, {5,5,7,1,1},
  {7,4,7,1,7}, {7,4,7,5,7}, {7,1,1,1,1}, {7,5,7,5,7}, {7,5,7,1,7},
};

static const int DIGIT_COL = 2;   // digit occupies cols 2..4
static const int DIGIT_ROW = 1;   // rows 1..5
static const int BAR_COL = 9;     // bar occupies cols 9..11
static const int BAR_WIDTH = 3;

Arduino_LED_Matrix matrix;
static uint8_t frame[ROWS * COLS];

static void render(int bucket, float intensity) {
  memset(frame, 0, sizeof(frame));
  if (bucket >= 0 && bucket <= 9) {
    for (int r = 0; r < 5; r++)
      for (int c = 0; c < 3; c++)
        if (DIGITS[bucket][r] & (4 >> c))
          frame[(DIGIT_ROW + r) * COLS + DIGIT_COL + c] = 1;
  }
  if (intensity < 0.0f) intensity = 0.0f;
  if (intensity > 1.0f) intensity = 1.0f;
  int lit = (int)(intensity * ROWS + 0.5f);   // 0..8 rows, filled from the bottom
  for (int r = 0; r < lit; r++)
    for (int c = 0; c < BAR_WIDTH; c++)
      frame[(ROWS - 1 - r) * COLS + BAR_COL + c] = 1;
  matrix.draw(frame);
}

void show(int bucket_index, float intensity) {
  render(bucket_index, intensity);
}

void clear_matrix() {
  memset(frame, 0, sizeof(frame));
  matrix.draw(frame);
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(1);
  clear_matrix();
  Bridge.begin();
  Bridge.provide_safe("show", show);
  Bridge.provide_safe("clear", clear_matrix);
}

void loop() {
}
