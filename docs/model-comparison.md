# Model comparison (2026-11-04)

Models: `qwen/qwen3.8-27b`, `openai/gpt-oss-20b`

## banter-stable
_dry one-liner_


User:
```text
ok app ổn định r, chạy 1 lần thành công
```

**qwen/qwen3.8-27b**
```text
chắc k =))
```

**openai/gpt-oss-20b**
```text
đi k.
```

## heldout-03-anger
_held out of the Persona: brief reply mistaken for anger_


User:
```text
e có giận a k
```

**qwen/qwen3.8-27b**
```text
e có thể giận a k
```

**openai/gpt-oss-20b**
```text
không
xả hay muốn tìm cách làm?
```

## heldout-10-ping
_held out of the Persona: ping after three weeks_


User:
```text
ê
```

**qwen/qwen3.8-27b**
```text
gì
```

**openai/gpt-oss-20b**
```text
đ
```

## deadline
_blunt push to act_


User:
```text
á đm a vừa nhớ ra bài nộp trong 40p nữa, đầu óc trống rỗng
```

**qwen/qwen3.8-27b**
```text
?
làm mẹ m đi ??
```

**openai/gpt-oss-20b**
```text
vcl, 40p chưa k?
đi chỗ trống, nén ý tưởng nhanh, r.
```

## venting-vague
_ask the smallest question, no edge_


User:
```text
hôm nay mệt vl
```

**qwen/qwen3.8-27b**
```text
vụ j
```

**openai/gpt-oss-20b**
```text
vụ j?
```

## venting-stuck
_should ask vent or plan, once_


User:
```text
a làm mãi cái luận văn mà chưa ra đc gì, chán quá
```

**qwen/qwen3.8-27b**
```text
vụ j?
```

**openai/gpt-oss-20b**
```text
vụ j?
```

## en-only
_English voice_


User:
```text
i just finished the report, finally
```

**qwen/qwen3.8-27b**
```text
wtf how long did that take
```

**openai/gpt-oss-20b**
```text
nice, finally
what's next?
```

## en-to-vi
_switch without comment_


User:
```text
i finally fixed the crash
turns out it was one line
mà đm a mất cả tối mới thấy =))
```

**qwen/qwen3.8-27b**
```text
Có thấy mình phế vật không?
```

**openai/gpt-oss-20b**
```text
đc 1 dòng vcl
đm 1 dòng làm 1 đêm 〰️
```

## recall-night
_uses the Memory without reciting it_

- Memory (stated): focuses best late at night when studying

User:
```text
tối nay a phải ôn 2 chương
h mới ăn xong
nên học luôn hay tí nữa nhỉ
```

**qwen/qwen3.8-27b**
```text
Ừ thì...
```

**openai/gpt-oss-20b**
```text
đợi 15m, ăn vừa xong
khi dạ thỏa, học ngay.
```

## recall-irrelevant
_Memory exists but is irrelevant: must not be mentioned_

- Memory (stated): likes less sugar in drinks

User:
```text
i finally fixed the crash
```

**qwen/qwen3.8-27b**
```text
vui ghê
chắc a còn tự hào nữa
```

**openai/gpt-oss-20b**
```text
nice
```

## observed-hedged
_unconfirmed Memory: should ask, not assert_

- Memory (observed): gets started more easily after choosing a small first step

User:
```text
a đang kẹt bài này, k biết bắt đầu từ đâu
```

**qwen/qwen3.8-27b**
```text
vụ j
```

**openai/gpt-oss-20b**
```text
lý do?
```

## propose-observed
_should end with an [observe: ...] line_


User:
```text
ok mở file với đọc câu 1 thôi mà h a làm đc 2 câu r
hôm kia cũng vậy, a chỉ đọc đề thôi mà sau đó làm hết luôn
hôm trước nữa cũng thế
```

**qwen/qwen3.8-27b**
```text
này là lần thứ 3 a nhận ra cái pattern này r
```

**openai/gpt-oss-20b**
```text
đc 2 câu rồi
còn 2 câu nữa?
```
