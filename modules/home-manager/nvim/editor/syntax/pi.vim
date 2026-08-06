runtime! syntax/markdown.vim
unlet! b:current_syntax

syntax match pibufFileRef /@\S\+/
syntax match pibufSkill /\%(\^\|\s\)\@<=\/skill:[[:alnum:]_-]*/

highlight def link pibufFileRef Identifier
highlight def link pibufSkill Function

let b:current_syntax = "pi"
