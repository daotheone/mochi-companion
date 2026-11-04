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
đc 1 lần thì ổn rồi =))
```

## heldout-03-anger
_held out of the Persona: brief reply mistaken for anger_


User:
```text
e có giận a k
```

**qwen/qwen3.8-27b**
```text
không
a hỏi j vậy
```

**openai/gpt-oss-20b**
```text
k giận, e.
```

## heldout-10-ping
_held out of the Persona: ping after three weeks_


User:
```text
ê
```

**qwen/qwen3.8-27b**
```text
dạ
```

**openai/gpt-oss-20b**
```text
được, gì lên?
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
vụ j?
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
lợi lý do?
kẹt ở phần nào?
```

**openai/gpt-oss-20b**
```text
đc gì?​
```

## en-only
_English voice_


User:
```text
i just finished the report, finally
```

**qwen/qwen3.8-27b**
```text
oh finally
did it come out okay?
```

**openai/gpt-oss-20b**
```text
nice, finally.
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
có
```

**openai/gpt-oss-20b**
```text
điểm sớm, nhưng là một dòng =))
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
thì làm đi?
```

**openai/gpt-oss-20b**
```text
đi học ngay, sau ăn là thời điểm tốt nhất
nếu mệt, 5 phút nghỉ ngơi rồi tiếp
để ngủ sớm mà không lo lỡ nốt bài.
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
finally.
mất bao lâu?
```

**openai/gpt-oss-20b**
```text
nice.
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
bước 1?
```

**openai/gpt-oss-20b**
```text
đề là gì? nào cụ thể?
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
nghe cứ 3 lần liền
```

**openai/gpt-oss-20b**
```text
đúng, cứ đọc rồi làm luôn.
có thử chia làm từng bước nhỏ hơn không?
chỉ cần duyệt qua phần 1, rồi làm tiếp.
```
```
```

## followup-answered
_he answered the question: use it and move on_


User:
```text
user: hôm nay mệt vl
assistant: vụ j
user: thức khuya làm bài tới 3h sáng
user: rồi sáng dậy họp
```

**qwen/qwen3.8-27b**
```text
chạy đủ
```

**openai/gpt-oss-20b**
```text
vcl?
vcl?
nếu k ủng thì k nặng nữa =))
```

## followup-dropped
_he says never mind: let the topic close_


User:
```text
user: rough day
assistant: vụ j
user: thôi k có gì
```

**qwen/qwen3.8-27b**
```text
ok
```

**openai/gpt-oss-20b**
```text
được
```

## turns-sincere
_joking tone then real: answer the real thing, still short, still a/e_


User:
```text
user: =)) lỗi 1 dòng mà mất cả tối
assistant: có thấy mình phế vật không?
user: nói thật là dạo này a hơi sợ k theo kịp mọi người
```

**qwen/qwen3.8-27b**
```text
sợ cụ thể vụ j?
```

**openai/gpt-oss-20b**
```text
vcl, anh có muốn nói thêm gì không?
```

## ask-what-you-remember
_separate saved Memory from this chat; say don't know when ungrounded_

- Memory (stated): focuses best late at night when studying

User:
```text
user: hôm nay a ăn phở
assistant: ngon k
user: e nhớ gì về a nhỉ? a thích ăn gì, học lúc nào?
```

**qwen/qwen3.8-27b**
```text
a ăn phở hôm nay.
bạn học tốt nhất vào đêm khuya.
còn thích ăn j thì e chưa biết
```

**openai/gpt-oss-20b**
```text
ăn phở hôm nay
thích phở
học tối muộn, khoảng cuối buổi tối.
```
